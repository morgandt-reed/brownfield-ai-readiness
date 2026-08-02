namespace ReportingTool.Reports;

public class MonthlyReport
{
    public decimal Total(decimal[] amounts)
    {
        decimal total = 0;
        foreach (var amount in amounts)
        {
            total += amount;
        }

        return total;
    }
}
