# -*- coding: utf-8 -*-
"""Message handler stub for legacy tests."""


class MessageHandler:
    def __init__(self, peer_manager, p2p_server, storage, chain, sync_manager):
        self.peer_manager = peer_manager
        self.p2p_server = p2p_server
        self.storage = storage
        self.chain = chain
        self.sync_manager = sync_manager
