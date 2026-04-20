"""
Intelligent Routing Decision Engine

Classifies requests and routes them to either Salesforce or Billing systems
based on keywords, issue type, context rules, and LLM-based classification.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum

logger = logging.getLogger(__name__)


class RoutingSystem(Enum):
    """Supported routing destinations"""
    SALESFORCE = "salesforce"
    BILLING = "billing"
    UNKNOWN = "unknown"


class RoutingClassifier:
    """
    Multi-factor routing classification system.
    
    Uses three priority levels:
    1. Keyword-based (fast)
    2. Issue type mapping (deterministic)
    3. Context rules (business logic)
    4. LLM-based (intelligent fallback)
    """
    
    # Keywords that strongly indicate billing-related requests
    BILLING_KEYWORDS = {
        "invoice", "billing", "payment", "charge", "charged",
        "refund", "refunded", "credit", "debit", "transaction",
        "account balance", "balance", "late payment", "billing period",
        "rate", "subscription", "discount", "coupon", "twice",
        "duplicate charge", "overcharge", "monthly", "amount", "cost"
    }
    
    # Keywords that strongly indicate Salesforce support tickets
    SF_KEYWORDS = {
        "bug", "issue", "problem", "ticket", "help", "support",
        "feature request", "complaint", "account access", "password",
        "login", "error", "feature enhancement", "documentation",
        "404", "403", "500", "timeout", "connection", "access denied",
        "cannot", "not working", "broken", "stuck", "unable"
    }
    
    # Issue type to system mapping
    ISSUE_TYPE_MAPPING = {
        # Billing mappings
        "billing_issue": RoutingSystem.BILLING,
        "payment_failed": RoutingSystem.BILLING,
        "invoice_query": RoutingSystem.BILLING,
        "refund_request": RoutingSystem.BILLING,
        "charge_dispute": RoutingSystem.BILLING,
        "subscription_issue": RoutingSystem.BILLING,
        
        # Support mappings
        "technical_support": RoutingSystem.SALESFORCE,
        "account_issue": RoutingSystem.SALESFORCE,
        "feature_request": RoutingSystem.SALESFORCE,
        "general_inquiry": RoutingSystem.SALESFORCE,
        "bug_report": RoutingSystem.SALESFORCE,
    }
    
    # Callable mapping for custom checks
    CONTEXT_RULES = []
    
    def score_keywords(self, text: str) -> Tuple[float, float]:
        """
        Score text against keyword lists.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (sf_score, billing_score) from 0 to 1
        """
        if not text:
            return 0.0, 0.0
        
        text_lower = text.lower()
        sf_matches = sum(1 for kw in self.SF_KEYWORDS if kw in text_lower)
        billing_matches = sum(1 for kw in self.BILLING_KEYWORDS if kw in text_lower)
        
        total = max(sf_matches + billing_matches, 1)
        sf_score = sf_matches / total if total > 0 else 0.0
        billing_score = billing_matches / total if total > 0 else 0.0
        
        return sf_score, billing_score
    
    def check_issue_type(self, issue_type: str) -> Optional[RoutingSystem]:
        """
        Check if issue type has explicit mapping.
        
        Args:
            issue_type: The issue type string
            
        Returns:
            RoutingSystem if found, None otherwise
        """
        issue_type_lower = issue_type.lower() if issue_type else ""
        return self.ISSUE_TYPE_MAPPING.get(issue_type_lower)
    
    def check_context_rules(self, state: Dict[str, Any]) -> Optional[Tuple[RoutingSystem, str]]:
        """
        Apply context-based business rules.
        
        Rules checked in order:
        1. Explicit payment amount present
        2. Billing period date range
        3. SF account/contact ID present
        4. Case/ticket number mentioned
        5. Billing field presence in backend_context
        
        Args:
            state: Agent state dict
            
        Returns:
            Tuple of (RoutingSystem, reason) if rule matches, None otherwise
        """
        message = state.get("message", "").lower()
        backend_context = state.get("backend_context", {})
        
        # Rule 1: Payment amount mentioned
        if any(word in message for word in ["$", "amount", "total", "cost"]):
            if any(marker in str(backend_context) for marker in ["amount", "payment", "price"]):
                return RoutingSystem.BILLING, "Payment amount detected in context"
        
        # Rule 2: Billing period date range
        if any(word in message for word in ["from", "to", "period", "month", "year"]):
            if "date" in message or "period" in message:
                return RoutingSystem.BILLING, "Billing period date range detected"
        
        # Rule 3: SF account/contact ID (would come from backend_context)
        if backend_context.get("case_id") or backend_context.get("contact_id"):
            return RoutingSystem.SALESFORCE, "SF object ID in context"
        
        # Rule 4: Case/ticket number
        if any(marker in message for marker in ["case #", "ticket #", "case number", "ticket number"]):
            return RoutingSystem.SALESFORCE, "Case/ticket reference found"
        
        # Rule 5: Billing fields in context
        billing_fields = {"invoice_id", "transaction_id", "billing_id", "payment_method"}
        if any(field in backend_context for field in billing_fields):
            return RoutingSystem.BILLING, f"Billing field detected: {[f for f in billing_fields if f in backend_context]}"
        
        return None
    
    def classify_with_llm(self, state: Dict[str, Any], llm_client) -> Tuple[RoutingSystem, float, str]:
        """
        Use LLM as fallback classifier for ambiguous cases.
        
        Args:
            state: Agent state
            llm_client: OpenAI client instance
            
        Returns:
            Tuple of (RoutingSystem, confidence, rationale)
        """
        prompt = f"""Classify whether this customer request should be handled by:

A) SALESFORCE (support tickets, case management, technical issues, feature requests)
B) BILLING (invoices, payments, refunds, charges, subscription issues)

Request Details:
- Issue Type: {state.get('issue_type', 'unknown')}
- Message: {state.get('message', '')}
- Category: {state.get('category', 'unknown')}

Respond with ONLY valid JSON, no markdown:
{{
  "system": "salesforce" or "billing",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}"""

        try:
            response = llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            system_str = result.get("system", "unknown").lower()
            
            system_map = {
                "salesforce": RoutingSystem.SALESFORCE,
                "billing": RoutingSystem.BILLING
            }
            system = system_map.get(system_str, RoutingSystem.UNKNOWN)
            confidence = float(result.get("confidence", 0.5))
            reasoning = result.get("reasoning", "LLM classification")
            
            return system, confidence, reasoning
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return RoutingSystem.UNKNOWN, 0.5, f"LLM error: {str(e)}"
    
    def classify_request(self, state: Dict[str, Any], llm_client=None) -> Dict[str, Any]:
        """
        Comprehensive multi-factor routing classification.
        
        Priority order:
        1. Issue type mapping (highest priority)
        2. Context rules (business logic)
        3. Keywords (heuristic)
        4. LLM classification (fallback)
        
        Args:
            state: Agent state dictionary
            llm_client: OpenAI client (optional)
            
        Returns:
            Classification result dict with:
            - target_system: RoutingSystem
            - confidence: float (0-1)
            - rationale: str
            - metadata: Dict with scoring details
        """
        
        metadata = {
            "keyword_matches": [],
            "rules_triggered": [],
            "scores": {}
        }
        
        # Priority 1: Issue Type Mapping
        system = self.check_issue_type(state.get("issue_type"))
        if system:
            return {
                "target_system": system,
                "confidence": 0.95,
                "rationale": f"Determined by issue type: {state.get('issue_type', 'general')}",
                "metadata": {**metadata, "classification_method": "issue_type_mapping"}
            }
        
        # Priority 2: Context Rules
        rule_result = self.check_context_rules(state)
        if rule_result:
            system, reason = rule_result
            return {
                "target_system": system,
                "confidence": 0.85,
                "rationale": reason,
                "metadata": {**metadata, "classification_method": "context_rules", "rules_triggered": [reason]}
            }
        
        # Priority 3: Keyword Analysis
        message = (state.get("message") or "")
        category = (state.get("category") or "")
        if not isinstance(message, str):
            message = str(message) if message else ""
        if not isinstance(category, str):
            category = str(category) if category else ""
        
        sf_score, billing_score = self.score_keywords(
            message + " " + category
        )
        
        metadata["scores"] = {"sf_score": sf_score, "billing_score": billing_score}
        
        if sf_score > billing_score and sf_score > 0.3:
            return {
                "target_system": RoutingSystem.SALESFORCE,
                "confidence": sf_score,
                "rationale": f"Keyword analysis (SF: {sf_score:.2f}, Billing: {billing_score:.2f})",
                "metadata": {**metadata, "classification_method": "keywords"}
            }
        
        if billing_score > sf_score and billing_score > 0.3:
            return {
                "target_system": RoutingSystem.BILLING,
                "confidence": billing_score,
                "rationale": f"Keyword analysis (Billing: {billing_score:.2f}, SF: {sf_score:.2f})",
                "metadata": {**metadata, "classification_method": "keywords"}
            }
        
        # Priority 4: LLM Classification (if client provided)
        if llm_client:
            system, confidence, reasoning = self.classify_with_llm(state, llm_client)
            if system != RoutingSystem.UNKNOWN:
                return {
                    "target_system": system,
                    "confidence": confidence,
                    "rationale": reasoning,
                    "metadata": {**metadata, "classification_method": "llm", "llm_confidence": confidence}
                }
        
        # Fallback: Unknown, flag for manual review
        return {
            "target_system": RoutingSystem.UNKNOWN,
            "confidence": 0.0,
            "rationale": "Could not confidently classify. Manual review recommended.",
            "metadata": {**metadata, "classification_method": "unknown"}
        }


# Global classifier instance
classifier = RoutingClassifier()


def classify_and_route(state: Dict[str, Any], llm_client=None) -> Dict[str, Any]:
    """
    Convenience function to classify and route a request.
    
    Args:
        state: Agent state
        llm_client: OpenAI client (optional)
        
    Returns:
        Classification result with routing decision
    """
    return classifier.classify_request(state, llm_client)
