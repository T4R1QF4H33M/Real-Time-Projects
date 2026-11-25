-- name: monthly_revenue
-- Monthly net revenue, orders, returns and month-over-month growth (window function).
WITH monthly AS (
    SELECT d.year, d.month, d.month_name,
           ROUND(SUM(f.net_amount), 2)                       AS net_revenue,
           SUM(CASE WHEN f.is_return = 0 THEN 1 ELSE 0 END)  AS orders,
           SUM(f.is_return)                                  AS returns
    FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year, d.month, d.month_name
)
SELECT year, month AS month_num, month_name, net_revenue, orders, returns,
       ROUND(100.0 * (net_revenue - LAG(net_revenue) OVER (ORDER BY year, month))
             / LAG(net_revenue) OVER (ORDER BY year, month), 1) AS mom_growth_pct
FROM monthly
ORDER BY year, month_num;

-- name: revenue_by_emirate
SELECT s.emirate, s.channel,
       COUNT(DISTINCT s.store_code)  AS stores,
       ROUND(SUM(f.net_amount), 2)   AS net_revenue,
       ROUND(100.0 * SUM(f.net_amount) / (SELECT SUM(net_amount) FROM fact_sales), 1) AS share_pct
FROM fact_sales f JOIN dim_store s ON f.store_key = s.store_key
GROUP BY s.emirate, s.channel
ORDER BY net_revenue DESC;

-- name: store_ranking
-- Store performance with rank and average basket value.
SELECT RANK() OVER (ORDER BY SUM(f.net_amount) DESC) AS rank,
       s.store_name, s.emirate,
       ROUND(SUM(f.net_amount), 2)                                       AS net_revenue,
       COUNT(*)                                                          AS transactions,
       ROUND(AVG(CASE WHEN f.is_return = 0 THEN f.net_amount END), 2)     AS avg_sale_value,
       ROUND(100.0 * SUM(f.is_return) / COUNT(*), 2)                      AS return_rate_pct
FROM fact_sales f JOIN dim_store s ON f.store_key = s.store_key
GROUP BY s.store_name, s.emirate
ORDER BY rank;

-- name: category_performance
SELECT p.category,
       SUM(f.quantity)                     AS units,
       ROUND(SUM(f.net_amount), 2)         AS net_revenue,
       ROUND(AVG(f.discount_pct) * 100, 1) AS avg_discount_pct
FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.category
ORDER BY net_revenue DESC;

-- name: top_products_per_category
-- Best-selling product in each category (ROW_NUMBER partitioned by category).
SELECT category, product_name, net_revenue
FROM (
    SELECT p.category, p.product_name, ROUND(SUM(f.net_amount), 2) AS net_revenue,
           ROW_NUMBER() OVER (PARTITION BY p.category ORDER BY SUM(f.net_amount) DESC) AS rn
    FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.category, p.product_name
)
WHERE rn = 1
ORDER BY net_revenue DESC;

-- name: weekend_vs_weekday
SELECT CASE d.is_weekend WHEN 1 THEN 'Weekend (Sat-Sun)' ELSE 'Weekday' END AS day_type,
       COUNT(DISTINCT d.date_key)                                   AS days,
       ROUND(SUM(f.net_amount) / COUNT(DISTINCT d.date_key), 2)     AS avg_daily_revenue
FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.is_weekend;

-- name: payment_mix
SELECT payment_method, COUNT(*) AS transactions,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM fact_sales), 1) AS share_pct
FROM fact_sales
GROUP BY payment_method
ORDER BY transactions DESC;

-- name: data_quality_summary
SELECT reject_reason, COUNT(*) AS rows
FROM quarantine_sales
GROUP BY reject_reason
ORDER BY rows DESC;
