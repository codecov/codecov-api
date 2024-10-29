import unittest
from billing.accounts import BankAccount

class TestBankAccount(unittest.TestCase):
    def test_init(self):
        account = BankAccount("John Doe", 100.0)
        self.assertEqual(account.owner, "John Doe")
        self.assertEqual(account.balance, 100.0)

    def test_init_negative_balance(self):
        with self.assertRaises(ValueError):
            BankAccount("John Doe", -50.0)

    def test_deposit(self):
        account = BankAccount("John Doe")
        self.assertEqual(account.deposit(50.0), 50.0)
        self.assertEqual(account.balance, 50.0)

    def test_deposit_negative_amount(self):
        account = BankAccount("John Doe")
        with self.assertRaises(ValueError):
            account.deposit(-50.0)

    def test_withdraw(self):
        account = BankAccount("John Doe", 100.0)
        self.assertEqual(account.withdraw(50.0), 50.0)
        self.assertEqual(account.balance, 50.0)

    def test_withdraw_negative_amount(self):
        account = BankAccount("John Doe", 100.0)
        with self.assertRaises(ValueError):
            account.withdraw(-50.0)

    def test_withdraw_insufficient_funds(self):
        account = BankAccount("John Doe", 50.0)
        with self.assertRaises(ValueError):
            account.withdraw(100.0)

    def test_transfer(self):
        account1 = BankAccount("John Doe", 100.0)
        account2 = BankAccount("Jane Doe", 50.0)
        balance1, balance2 = account1.transfer(account2, 30.0)
        self.assertEqual(balance1, 70.0)
        self.assertEqual(balance2, 80.0)
        self.assertEqual(account1.balance, 70.0)
        self.assertEqual(account2.balance, 80.0)

    def test_transfer_invalid_recipient(self):
        account = BankAccount("John Doe", 100.0)
        with self.assertRaises(ValueError):
            account.transfer("not an account", 50.0)

    def test_transfer_insufficient_funds(self):
        account1 = BankAccount("John Doe", 50.0)
        account2 = BankAccount("Jane Doe", 50.0)
        with self.assertRaises(ValueError):
            account1.transfer(account2, 100.0)

    def test_get_balance(self):
        account = BankAccount("John Doe", 100.0)
        self.assertEqual(account.get_balance(), 100.0)

if __name__ == '__main__':
    unittest.main()