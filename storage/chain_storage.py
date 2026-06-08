class ChainStorage:
    def __init__(self):
        self.blocks = []
    def get_blocks_count(self):
        return len(self.blocks)
    def save_block(self, height, hash, prev_hash, miner, txs):
        self.blocks.append({"height": height, "hash": hash})
    def get_last_block(self):
        return self.blocks[-1] if self.blocks else None
chain_storage = ChainStorage()
