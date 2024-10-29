import unittest
from billing.accounts import BankAccount

class TestBankAccount(unittest.TestCase):
    def setUp(self):
        self.account = BankAccount("John Doe", 1000.0)

    def test_initialization(self):
        self.assertEqual(self.account.owner, "John Doe")
        self.assertEqual(self.account.balance, 1000.0)

    def test_initialization_with_negative_balance(self):
        with self.assertRaises(ValueError):
            BankAccount("Jane Doe", -100.0)

    def test_deposit(self):
        new_balance = self.account.deposit(500.0)
        self.assertEqual(new_balance, 1500.0)
        self.assertEqual(self.account.balance, 1500.0)

    def test_deposit_negative_amount(self):
        with self.assertRaises(ValueError):
            self.account.deposit(-100.0)

    def test_withdraw(self):
        new_balance = self.account.withdraw(300.0)
        self.assertEqual(new_balance, 700.0)
        self.assertEqual(self.account.balance, 700.0)

    def test_withdraw_negative_amount(self):
        with self.assertRaises(ValueError):
            self.account.withdraw(-100.0)

    def test_withdraw_insufficient_funds(self):
        with self.assertRaises(ValueError):
            self.account.withdraw(1500.0)

    def test_transfer(self):
        other_account = BankAccount("Jane Doe", 500.0)
        sender_balance, recipient_balance = self.account.transfer(other_account, 300.0)
        self.assertEqual(sender_balance, 700.0)
        self.assertEqual(recipient_balance, 800.0)
        self.assertEqual(self.account.balance, 700.0)
        self.assertEqual(other_account.balance, 800.0)

    def test_transfer_invalid_recipient(self):
        with self.assertRaises(ValueError):
            self.account.transfer("not a bank account", 100.0)

    def test_transfer_insufficient_funds(self):
        other_account = BankAccount("Jane Doe", 500.0)
        with self.assertRaises(ValueError):
            self.account.transfer(other_account, 1500.0)

    def test_get_balance(self):
        self.assertEqual(self.account.get_balance(), 1000.0)

if __name__ == '__main__':
    unittest.main()