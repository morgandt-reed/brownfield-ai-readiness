package com.example.portal;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class CustomerServiceTest {
    @Test
    void joinsNames() {
        assertEquals("Ada Lovelace", new CustomerService().displayName("Ada", "Lovelace"));
    }
}
