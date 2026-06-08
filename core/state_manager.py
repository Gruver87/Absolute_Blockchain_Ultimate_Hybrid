class StateManager:
    def __init__(self):
        self.balances = {"0x94f45b97f9bc27": 1000000}
    def get_balance(self, address):
        return self.balances.get(address, 0)
    def set_balance(self, address, amount):
        self.balances[address] = amount
    def transfer(self, fr, to, amt):
        if self.balances.get(fr, 0) < amt:
            return False
        self.balances[fr] -= amt
        self.balances[to] = self.balances.get(to, 0) + amt
        return True
state_manager = StateManager()
