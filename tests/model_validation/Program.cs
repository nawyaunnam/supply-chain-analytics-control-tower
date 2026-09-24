using Microsoft.AnalysisServices.Tabular;
var db = JsonSerializer.DeserializeDatabase(File.ReadAllText(args[0]),null,Microsoft.AnalysisServices.CompatibilityMode.PowerBI);
if (db.Model.Tables.Count < 12) throw new Exception("Incomplete model");
if (db.Model.Roles.Find("Warehouse Analyst") is null) throw new Exception("RLS role missing");
if (db.Model.Tables["Metrics"].Measures.Count < 25) throw new Exception("Measures missing");
Console.WriteLine($"Power BI TOM validation passed: {db.Model.Tables.Count} tables and {db.Model.Relationships.Count} relationships.");
