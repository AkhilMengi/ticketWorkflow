# Salesforce Setup Guide for Contract Creation

## Quick Setup (5 minutes)

### Step 1: Log in to Salesforce
1. Go to your Salesforce org (usually `https://your-instance.salesforce.com`)
2. Log in with your credentials

### Step 2: Create Custom Fields on Contract Object

Navigate to: **Setup → Object Manager → Contract**

#### Field 1: Tenant Name
1. Click **Fields & Relationships**
2. Click **New**
3. Select **Text** → Next
4. Fill in:
   - **Field Label**: `Tenant Name`
   - **Field Name**: `Tenant_Name` (will become `Tenant_Name__c`)
   - **Length**: `255`
   - **Required**: ✓ Checked
5. Click **Save**

#### Field 2: Property Address
1. Click **New**
2. Select **Text Area (Long)** → Next
3. Fill in:
   - **Field Label**: `Property Address`
   - **Field Name**: `Property_Address` (will become `Property_Address__c`)
   - **Columns**: `80`
   - **Rows**: `5`
   - **Required**: ✓ Checked
4. Click **Save**

#### Field 3: Move-In Date
1. Click **New**
2. Select **Date** → Next
3. Fill in:
   - **Field Label**: `Move In Date`
   - **Field Name**: `Move_In_Date` (will become `Move_In_Date__c`)
   - **Required**: ✓ Checked
4. Click **Save**

#### Field 4: Move-Out Date
1. Click **New**
2. Select **Date** → Next
3. Fill in:
   - **Field Label**: `Move Out Date`
   - **Field Name**: `Move_Out_Date` (will become `Move_Out_Date__c`)
   - **Required**: ☐ Unchecked (optional)
4. Click **Save**

#### Field 5: Monthly Rent
1. Click **New**
2. Select **Currency** → Next
3. Fill in:
   - **Field Label**: `Monthly Rent`
   - **Field Name**: `Monthly_Rent` (will become `Monthly_Rent__c`)
   - **Decimal Places**: `2`
   - **Required**: ✓ Checked
4. Click **Save**

#### Field 6: External User ID
1. Click **New**
2. Select **Text** → Next
3. Fill in:
   - **Field Label**: `External User ID`
   - **Field Name**: `External_User_Id` (will become `External_User_Id__c`)
   - **Length**: `255`
   - **Required**: ☐ Unchecked (optional)
4. Click **Save**

#### Field 7: Source App
1. Click **New**
2. Select **Text** → Next
3. Fill in:
   - **Field Label**: `Source App`
   - **Field Name**: `Source_App` (will become `Source_App__c`)
   - **Length**: `100`
   - **Required**: ☐ Unchecked (optional)
4. Click **Save**

#### Field 8: Backend Context
1. Click **New**
2. Select **Text Area (Long)** → Next
3. Fill in:
   - **Field Label**: `Backend Context`
   - **Field Name**: `Backend_Context` (will become `Backend_Context__c`)
   - **Columns**: `80`
   - **Rows**: `10`
   - **Required**: ☐ Unchecked (optional)
4. Click **Save**

### Step 3: Verify API Connection (Optional)

Run the test file to verify Salesforce connection:
```bash
python test_sf.py
```

Expected output:
```
Salesforce login successful
Successfully authenticated with Salesforce: https://your-instance.my.salesforce.com
```

---

## Verification Checklist

After creating the fields, verify they exist:

✓ **Navigate to**: Setup → Object Manager → Contract → Fields & Relationships

You should see all 8 fields listed:
- [x] Tenant Name (Tenant_Name__c)
- [x] Property Address (Property_Address__c)
- [x] Move In Date (Move_In_Date__c)
- [x] Move Out Date (Move_Out_Date__c)
- [x] Monthly Rent (Monthly_Rent__c)
- [x] External User ID (External_User_Id__c)
- [x] Source App (Source_App__c)
- [x] Backend Context (Backend_Context__c)

---

## Testing Contract Creation

Once fields are created, test the API:

```bash
curl -X POST http://localhost:8000/api/contracts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "tenant_name": "John Doe",
    "property_address": "123 Main Street, Apt 4B, New York, NY 10001",
    "move_in_date": "2026-05-15",
    "move_out_date": "2027-05-14",
    "rent_amount": 2500.00
  }'
```

Expected response:
```json
{
  "job_id": "xxxx-xxxx-xxxx-xxxx",
  "status": "queued"
}
```

Then poll the status:
```bash
curl -X GET http://localhost:8000/api/contracts/xxxx-xxxx-xxxx-xxxx
```

Expected completed response:
```json
{
  "job_id": "xxxx-xxxx-xxxx-xxxx",
  "status": "completed",
  "result": {
    "status": "success",
    "contract_id": "a0E2X000000IZ3ZUAW",
    "tenant_name": "John Doe",
    "property_address": "123 Main Street, Apt 4B, New York, NY 10001",
    "move_in_date": "2026-05-15",
    "move_out_date": "2027-05-14",
    "rent_amount": 2500.00,
    "message": "Contract #a0E2X000000IZ3ZUAW created successfully"
  }
}
```

---

## Troubleshooting

### Issue: "INVALID_FIELD" Error

**Problem**: Fields don't exist in Salesforce
**Solution**: Verify all 8 custom fields were created correctly

### Issue: "Authentication Failed" Error

**Problem**: SF credentials invalid or expired
**Solution**: Check `.env` file for correct:
- `SF_LOGIN_URL`
- `SF_CLIENT_ID`
- `SF_CLIENT_SECRET`

### Issue: Contract Created But Fields Blank

**Problem**: Fields created but permissions not set
**Solution**: 
1. Go to Setup → Object Manager → Contract → Field-Level Security
2. Select your user profile
3. Ensure all custom fields are marked "Visible" and "Editable"

### Issue: "Required field missing" Error

**Problem**: Required fields not provided in API payload
**Solution**: Ensure all required fields in request:
- user_id
- tenant_name
- property_address
- move_in_date
- rent_amount

### Issue: API Returns 404 Not Found

**Problem**: Job ID endpoint malformed
**Solution**: Use exact job_id from create response, example:
```bash
curl -X GET http://localhost:8000/api/contracts/f47ac10b-58cc-4372-a567-0e02b2c3d479
```

---

## Advanced Setup

### Add Validation Rules (Optional)

Navigate to: **Setup → Object Manager → Contract → Validation Rules** → New

**Rule: Move-Out After Move-In**
```
AND(
  NOT(ISBLANK(Move_Out_Date__c)),
  Move_Out_Date__c <= Move_In_Date__c
)
```
Error Message: "Move-out date must be after move-in date"

**Rule: Rent Amount Greater Than Zero**
```
Monthly_Rent__c <= 0
```
Error Message: "Monthly rent amount must be greater than zero"

### Add to Page Layout (Optional)

1. Navigate to: **Setup → Object Manager → Contract → Page Layouts**
2. Click **Contract Layout** (or your default layout)
3. Click **Edit**
4. Drag these fields to a section (or create "Property Information" section):
   - Tenant Name
   - Property Address
   - Move In Date
   - Move Out Date
   - Monthly Rent
   - External User ID
   - Source App
5. Click **Save**

---

## Next Steps

1. ✅ Create all 8 custom fields
2. ✅ Test connection with `test_sf.py`
3. ✅ Run contract creation test
4. ✅ Verify contract appears in Salesforce

Once complete, your contract creation workflow is fully functional!

---

## Field Summary Table

| Field Name | API Name | Type | Required | Purpose |
|------------|----------|------|----------|---------|
| Tenant Name | Tenant_Name__c | Text(255) | Yes | Occupant name |
| Property Address | Property_Address__c | LongText(32k) | Yes | Property location |
| Move In Date | Move_In_Date__c | Date | Yes | Lease start date |
| Move Out Date | Move_Out_Date__c | Date | No | Lease end date |
| Monthly Rent | Monthly_Rent__c | Currency | Yes | Rent amount |
| External User ID | External_User_Id__c | Text(255) | No | External reference |
| Source App | Source_App__c | Text(100) | No | Application name |
| Backend Context | Backend_Context__c | LongText(32k) | No | JSON metadata |
