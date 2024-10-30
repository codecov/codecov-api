import unittest

from billing.accounts import BankAccount


class TestBankAccount(unittest.TestCase):
    def setUp(self):
        self.account = BankAccount("John Doe", 100.0)

    def test_init(self):
        self.assertEqual(self.account.owner, "John Doe")
        self.assertEqual(self.account.balance, 100.0)
        with self.assertRaises(ValueError):
            BankAccount("Jane Doe", -50.0)

    def test_deposit(self):
        new_balance = self.account.deposit(50.0)
        self.assertEqual(new_balance, 150.0)
        self.assertEqual(self.account.balance, 150.0)
        with self.assertRaises(ValueError):
            self.account.deposit(-10.0)
        with self.assertRaises(ValueError):
            self.account.deposit(0)

    def test_withdraw(self):
        new_balance = self.account.withdraw(50.0)
        self.assertEqual(new_balance, 50.0)
        self.assertEqual(self.account.balance, 50.0)
        with self.assertRaises(ValueError):
            self.account.withdraw(-10.0)
        with self.assertRaises(ValueError):
            self.account.withdraw(0)
        with self.assertRaises(ValueError):
            self.account.withdraw(1000.0)

    def test_transfer(self):
        other_account = BankAccount("Jane Doe", 50.0)
        balances = self.account.transfer(other_account, 30.0)
        self.assertEqual(balances, (70.0, 80.0))
        self.assertEqual(self.account.balance, 70.0)
        self.assertEqual(other_account.balance, 80.0)

        with self.assertRaises(ValueError):
            self.account.transfer(other_account, -10.0)
        with self.assertRaises(ValueError):
            self.account.transfer(other_account, 0)
        with self.assertRaises(ValueError):
            self.account.transfer(other_account, 1000.0)
        with self.assertRaises(ValueError):
            self.account.transfer("not an account", 10.0)

    def test_get_balance(self):
        self.assertEqual(self.account.get_balance(), 100.0)
        self.account.deposit(50.0)
        self.assertEqual(self.account.get_balance(), 150.0)
        self.account.withdraw(30.0)
        self.assertEqual(self.account.get_balance(), 120.0)


if __name__ == "__main__":
    unittest.main()
