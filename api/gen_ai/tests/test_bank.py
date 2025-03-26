import unittest
from datetime import datetime
from unittest.mock import patch

from api.gen_ai.bank import BankAccountManager


class TestBankAccountManager(unittest.TestCase):
    def setUp(self):
        self.manager = BankAccountManager()
        self.account_id = self.manager.create_account("Test User")

    def test_create_account(self):
        """Test that an account can be created with correct initial values."""
        account = self.manager.accounts[self.account_id]
        self.assertEqual(account['owner'], "Test User")
        self.assertEqual(account['balance'], 0.0)
        self.assertIsInstance(account['transactions'], list)
        self.assertEqual(len(account['transactions']), 0)
        self.assertIsInstance(account['created_at'], datetime)

    @patch('uuid.uuid4')
    def test_create_account_id(self, mock_uuid):
        """Test that an account ID is created correctly using UUID."""
        mock_uuid.return_value = "mock-uuid-123"
        manager = BankAccountManager()
        account_id = manager.create_account("Test User")
        self.assertEqual(account_id, "mock-uuid-123")

    def test_deposit_valid_amount(self):
        """Test depositing a valid amount into an account."""
        new_balance = self.manager.deposit(self.account_id, 100.0)
        self.assertEqual(new_balance, 100.0)
        self.assertEqual(self.manager.accounts[self.account_id]['balance'], 100.0)
        
        # Verify transaction was recorded
        transactions = self.manager.accounts[self.account_id]['transactions']
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]['type'], 'deposit')
        self.assertEqual(transactions[0]['amount'], 100.0)
        self.assertIsInstance(transactions[0]['timestamp'], datetime)

    def test_deposit_multiple_amounts(self):
        """Test multiple deposits into an account."""
        self.manager.deposit(self.account_id, 100.0)
        new_balance = self.manager.deposit(self.account_id, 50.0)
        self.assertEqual(new_balance, 150.0)
        self.assertEqual(len(self.manager.accounts[self.account_id]['transactions']), 2)

    def test_deposit_invalid_amount(self):
        """Test that depositing zero or negative amount raises ValueError."""
        with self.assertRaises(ValueError) as context:
            self.manager.deposit(self.account_id, 0)
        self.assertIn("Deposit amount must be positive", str(context.exception))

        with self.assertRaises(ValueError) as context:
            self.manager.deposit(self.account_id, -50)
        self.assertIn("Deposit amount must be positive", str(context.exception))

    def test_withdraw_valid_amount(self):
        """Test withdrawing a valid amount from an account."""
        self.manager.deposit(self.account_id, 100.0)
        new_balance = self.manager.withdraw(self.account_id, 50.0)
        self.assertEqual(new_balance, 50.0)
        
        # Verify transaction was recorded
        transactions = self.manager.accounts[self.account_id]['transactions']
        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[1]['type'], 'withdrawal')
        self.assertEqual(transactions[1]['amount'], 50.0)

    def test_withdraw_insufficient_funds(self):
        """Test that withdrawing more than balance raises ValueError."""
        self.manager.deposit(self.account_id, 50.0)
        with self.assertRaises(ValueError) as context:
            self.manager.withdraw(self.account_id, 100.0)
        self.assertIn("Insufficient funds", str(context.exception))

    def test_withdraw_invalid_amount(self):
        """Test that withdrawing zero or negative amount raises ValueError."""
        with self.assertRaises(ValueError) as context:
            self.manager.withdraw(self.account_id, 0)
        self.assertIn("Withdrawal amount must be positive", str(context.exception))

    def test_transfer_between_accounts(self):
        """Test transferring money between two accounts."""
        second_account_id = self.manager.create_account("Second User")
        self.manager.deposit(self.account_id, 100.0)
        
        result = self.manager.transfer(self.account_id, second_account_id, 50.0)
        self.assertTrue(result)
        self.assertEqual(self.manager.get_balance(self.account_id), 50.0)
        self.assertEqual(self.manager.get_balance(second_account_id), 50.0)

    def test_transfer_to_same_account(self):
        """Test that transferring to the same account raises ValueError."""
        with self.assertRaises(ValueError) as context:
            self.manager.transfer(self.account_id, self.account_id, 50.0)
        self.assertIn("Cannot transfer to the same account", str(context.exception))

    def test_get_transaction_history(self):
        """Test retrieving transaction history for an account."""
        self.manager.deposit(self.account_id, 100.0)
        self.manager.withdraw(self.account_id, 50.0)
        
        history = self.manager.get_transaction_history(self.account_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['type'], 'deposit')
        self.assertEqual(history[1]['type'], 'withdrawal')

    def test_delete_account(self):
        """Test that an account can be deleted."""
        result = self.manager.delete_account(self.account_id)
        self.assertTrue(result)
        self.assertNotIn(self.account_id, self.manager.accounts)