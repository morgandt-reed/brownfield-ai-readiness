package com.example.batch;

import java.io.File;

public class NightlyJob {
    public static void main(String[] args) {
        File input = new File(args[0]);
        System.out.println("processing " + input.getName());
    }
}
