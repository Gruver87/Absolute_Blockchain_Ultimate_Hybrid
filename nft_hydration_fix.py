# ============================================================
# NFT DATABASE HYDRATION FIX
# ============================================================

import json
import sqlite3

def apply_nft_hydration_fix(nft_manager, db):
    """Загружает NFT из базы данных в память"""
    loaded = 0
    print('🦋 Загрузка NFT из базы данных...')
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT token_id, collection_id, name, owner_address, 
                       creator_address, metadata, price, for_sale 
                FROM nft_tokens
            ''')
            rows = cursor.fetchall()
            
            print(f'📦 Найдено {len(rows)} NFT в базе данных')
            
            for row in rows:
                token_id = row['token_id']
                
                if token_id in nft_manager.tokens:
                    continue
                
                # Создаём объект NFT
                token = {
                    'token_id': token_id,
                    'collection_id': row['collection_id'],
                    'name': row['name'],
                    'owner': row['owner_address'],
                    'creator': row['creator_address'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else {},
                    'price': row['price'] or 0,
                    'for_sale': row['for_sale'] == 1
                }
                
                nft_manager.tokens[token_id] = token
                loaded += 1
            
            print(f'🎉 Загружено {loaded} NFT в память')
            return loaded
            
    except Exception as e:
        print(f'❌ Ошибка загрузки NFT: {e}')
        return 0
