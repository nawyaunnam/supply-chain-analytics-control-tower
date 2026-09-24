-- Select the tower_<batch_id> Glue database only after curated/<batch_id>/_READY.json exists.
-- Athena reads raw curated facts for exploration; tested dimensional marts are built in Redshift.
SELECT warehouse_id, snapshot_date,
       SUM(on_hand_qty) AS units_on_hand,
       SUM(CASE WHEN on_hand_qty=0 THEN 1 ELSE 0 END) AS stockout_skus
FROM inventory GROUP BY warehouse_id,snapshot_date ORDER BY snapshot_date DESC;

SELECT carrier, COUNT(*) AS shipments,
       AVG(date_diff('day',shipped_date,delivered_date)) AS average_transit_days
FROM shipments WHERE delivered_date IS NOT NULL GROUP BY carrier;
