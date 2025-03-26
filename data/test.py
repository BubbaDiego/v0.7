#!/usr/bin/env python3
from datetime import datetime
from data.data_locker import DataLocker

def insert_sol_price():
    # Get the singleton instance of DataLocker
    dl = DataLocker.get_instance()
    # Insert or update the SOL price with a current price of 145.67 and source "Manual"
    dl.insert_or_update_price("SOL", 145.67, "Manual", datetime.now())
    print("Inserted SOL price: 145.67")

if __name__ == "__main__":
    insert_sol_price()
