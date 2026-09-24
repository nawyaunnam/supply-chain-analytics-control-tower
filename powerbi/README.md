# Supply Chain Power BI project

Open ControlTower.pbip in Power BI Desktop on Windows with PBIP/PBIR support enabled. Set DataFolder to the generated artifacts directory, then Refresh. Import theme.json and mark Date using date_day. CSV import works with both DuckDB and PostgreSQL exports; set UseRedshift=true and configure RedshiftServer/RedshiftDatabase for a live Redshift connection.

Six report pages: executive overview, inventory health, supplier performance, demand forecasting, anomaly investigation, and warehouse drill-through. The semantic model contains 30 explicit DAX measures and typed Power Query functions. Orders, shipments, inventory, receipts and model predictions remain separate facts to prevent multiplied totals.

Warehouse Analyst RLS filters Warehouse through a USERPRINCIPALNAME entitlement table, and one-way relationships propagate to every operational fact. Replace the three example.com identities with governed entitlements. Test W01/W02/W03 and an unknown identity with View as. Dimension labels are shared master data; RLS restricts fact values. Workspace editors are not equivalent to Service viewers for RLS validation.

Order OTIF cannot be sliced by Product without changing its order-wide meaning; the overview deliberately uses date/warehouse controls. Supplier filters affect procurement facts, not sales inventory. Anomaly SKU `ALL` means a warehouse-level delivery observation; Product slicers do not hide warehouse-level alerts. Forecast target dates extend beyond historical Date and use their own axis. Historical date filters do not change an already-issued future forecast.

Use the forecast page's SKU and warehouse slicers to inspect individual series and empirical bands. Backtest metrics compare model rows, not mixed model totals. Lower/upper bands are not calibrated portfolio intervals. Date-window turnover is not annualized.

CI validates PBIR with Microsoft's published schemas and deserializes model.bim using Microsoft TOM. **Desktop rendering, DAX-engine execution and Service RLS have not been verified on macOS.** Complete these checks before deployment:

- Refresh all CSV/Redshift sources; confirm null delivery/receipt dates load.
- Compare OTIF and fill-rate results against mart_service_monthly.csv; the golden test is 1/3 OTIF and 72% fill.
- Verify inventory period ratios from daily totals, not sums of SKU ratios.
- Test warehouse drill-through and all visual bindings.
- Test RLS with each authorized and unknown identity as Service Viewers.
- Run Performance Analyzer and inspect Redshift query history for query folding; retain evidence from the actual deployment.

This bounded example performs full refreshes. Production incremental partitions must account for late shipment receipts and corrections; a naive max-date watermark would miss them. No refresh performance or scale benchmark is invented here.
