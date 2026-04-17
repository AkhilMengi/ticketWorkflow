from app.integrations.salesforce import SalesforceClient

sf = SalesforceClient()

result = sf.create_case(
    subject="Python Backend Test Case",
    description="Testing Salesforce case creation from Python backend"
)

print(result)