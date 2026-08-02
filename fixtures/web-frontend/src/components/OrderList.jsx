export function OrderList({ orders }) {
  return orders.map((order) => order.id);
}
