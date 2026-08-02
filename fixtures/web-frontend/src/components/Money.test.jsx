import { format } from "./Money";

test("formats cents as a decimal amount", () => {
  expect(format(1250)).toBe("12.50");
});
