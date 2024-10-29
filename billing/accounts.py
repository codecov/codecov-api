class BankAccount:
    def __init__(self, owner, balance=0.0):
        self.owner = owner
        if balance < 0:
            raise ValueError("Initial balance cannot be negative")
        self.balance = balance

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self.balance += amount
        return self.balance

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount
        return self.balance

    def transfer(self, other_account, amount):
        if not isinstance(other_account, BankAccount):
            raise ValueError("Recipient must be a BankAccount instance")
        self.withdraw(amount)
        other_account.deposit(amount)
        return self.balance, other_account.balance

    def get_balance(self):
        return self.balance
