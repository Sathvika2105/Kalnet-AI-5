import json
from datetime import datetime
from typing import List, Dict, Any

class MockWorksheet:
    def __init__(self, data: List[Dict]):
        self.data = data
    
    def get_all_records(self) -> List[Dict]:
        return self.data
    
    def update_cell(self, row: int, col: int, value: Any):
        # Adjust for header row (row 2 = index 0 in data)
        data_index = row - 2
        if 0 <= data_index < len(self.data):
            col_names = ['lead_id', 'name', 'email', 'company', 'email_sent_at', 
                        'sequence_step', 'replied']
            field = col_names[col - 1]
            self.data[data_index][field] = value
            print(f"MOCK: Updated cell ({row}, {col}) with value: {value}")

class MockClient:
    def __init__(self):
        # Sample demo data
        self.demo_data = [
            {
                "lead_id": "1001",
                "name": "John Smith",
                "email": "john@example.com", 
                "company": "Tech Corp",
                "email_sent_at": "2024-01-15",
                "sequence_step": 1,
                "replied": "FALSE"
            },
            {
                "lead_id": "1002",
                "name": "Sarah Johnson",
                "email": "sarah@example.com",
                "company": "Innovate Ltd",
                "email_sent_at": "",
                "sequence_step": 0,
                "replied": "FALSE"
            },
            {
                "lead_id": "1003",
                "name": "Mike Brown",
                "email": "mike@example.com",
                "company": "Global Solutions",
                "email_sent_at": "2024-01-14",
                "sequence_step": 2,
                "replied": "TRUE"
            }
        ]
    
    def open(self, sheet_name: str):
        return MockSpreadsheet(self.demo_data)

    def open_by_key(self, key: str):
        return MockSpreadsheet(self.demo_data)

class MockSpreadsheet:
    def __init__(self, data: List[Dict]):
        self.sheet1 = MockWorksheet(data)

# Replace the actual gspread import with mock for demo
def mock_authorize(creds):
    return MockClient()