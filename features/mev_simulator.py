#!/usr/bin/env python3
"""Compatibility wrapper for the renamed MEV analyzer module."""

from features.mev_analyzer import MEVAnalyzer, Transaction


# Backward-compatible import name for older callers.
MEVSimulator = MEVAnalyzer
