import uuid
import datetime


class BankAccountManager:
    def __init__(self):
        self.accounts = {}

    def create_account(self, owner_name):
        account_id = str(uuid.uuid4())
        self.accounts[account_id] = {
            'owner': owner_name,
            'balance': 0.0,
            'transactions': [],
            'created_at': datetime.datetime.utcnow()
        }
        return account_id

    def deposit(self, account_id, amount):
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        account = self._get_account(account_id)
        account['balance'] += amount
        account['transactions'].append({
            'type': 'deposit',
            'amount': amount,
            'timestamp': datetime.datetime.utcnow()
        })
        return account['balance']

    def withdraw(self, account_id, amount):
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        account = self._get_account(account_id)
        if account['balance'] < amount:
            raise ValueError("Insufficient funds")
        account['balance'] -= amount
        account['transactions'].append({
            'type': 'withdrawal',
            'amount': amount,
            'timestamp': datetime.datetime.utcnow()
        })
        return account['balance']

    def transfer(self, from_account_id, to_account_id, amount):
        if from_account_id == to_account_id:
            raise ValueError("Cannot transfer to the same account")
        self.withdraw(from_account_id, amount)
        self.deposit(to_account_id, amount)
        return True

    def get_balance(self, account_id):
        return self._get_account(account_id)['balance']

    def get_transaction_history(self, account_id):
        return list(self._get_account(account_id)['transactions'])

    def delete_account(self, account_id):
        if account_id not in self.accounts:
            raise ValueError("Account does not exist")
        del self.accounts[account_id]
        return True

    def _get_account(self, account_id):
        if account_id not in self.accounts:
            raise ValueError("Account not found")
        return self.accounts[account_id]
