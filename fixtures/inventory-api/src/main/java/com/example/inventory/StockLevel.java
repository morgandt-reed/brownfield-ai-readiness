package com.example.inventory;

public class StockLevel {
    private final int onHand;

    public StockLevel(int onHand) {
        this.onHand = onHand;
    }

    public boolean available(int wanted) {
        return wanted <= onHand;
    }
}
