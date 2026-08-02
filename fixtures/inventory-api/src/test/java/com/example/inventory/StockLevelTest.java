package com.example.inventory;

import static org.junit.jupiter.api.Assertions.assertFalse;

import org.junit.jupiter.api.Test;

class StockLevelTest {
    @Test
    void refusesWhenShort() {
        assertFalse(new StockLevel(2).available(5));
    }
}
