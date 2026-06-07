from core.blockchain import Blockchain

bc = Blockchain()

print("=" * 60)
print("BLOCKCHAIN AUDIT")
print("=" * 60)

print("Height:", bc.get_height())

for i in range(bc.get_height()):
    try:
        block = bc.get_block(i)

        txs = block.get("transactions", [])

        print(
            f"Block {i} | "
            f"txs={len(txs)} | "
            f"hash={block.get('hash')}"
        )

    except Exception as e:
        print(f"ERROR block {i}: {e}")