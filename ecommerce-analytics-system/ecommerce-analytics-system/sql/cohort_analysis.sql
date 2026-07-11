-- cohort, retention and rfm-style segmentation

-- cohort = month of first completed order
WITH first_purchase AS (
    SELECT
        customer_id,
        MIN(strftime('%Y-%m', order_date)) AS cohort_month
    FROM orders
    WHERE status = 'Completed'
    GROUP BY customer_id
)
SELECT cohort_month, COUNT(*) AS customers_in_cohort
FROM first_purchase
GROUP BY cohort_month
ORDER BY cohort_month;


-- monthly retention rate per cohort
WITH first_purchase AS (
    SELECT
        customer_id,
        MIN(strftime('%Y-%m', order_date)) AS cohort_month
    FROM orders
    WHERE status = 'Completed'
    GROUP BY customer_id
),
activity AS (
    SELECT DISTINCT
        o.customer_id,
        strftime('%Y-%m', o.order_date) AS activity_month
    FROM orders o
    WHERE o.status = 'Completed'
),
cohort_activity AS (
    SELECT
        fp.cohort_month,
        a.activity_month,
        (CAST(strftime('%Y', a.activity_month || '-01') AS INTEGER) * 12 +
         CAST(strftime('%m', a.activity_month || '-01') AS INTEGER)) -
        (CAST(strftime('%Y', fp.cohort_month || '-01') AS INTEGER) * 12 +
         CAST(strftime('%m', fp.cohort_month || '-01') AS INTEGER)) AS month_index,
        a.customer_id
    FROM first_purchase fp
    JOIN activity a ON fp.customer_id = a.customer_id
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM first_purchase
    GROUP BY cohort_month
)
SELECT
    ca.cohort_month,
    ca.month_index,
    COUNT(DISTINCT ca.customer_id) AS active_customers,
    cs.cohort_size,
    ROUND(100.0 * COUNT(DISTINCT ca.customer_id) / cs.cohort_size, 1) AS retention_pct
FROM cohort_activity ca
JOIN cohort_sizes cs ON ca.cohort_month = cs.cohort_month
GROUP BY ca.cohort_month, ca.month_index, cs.cohort_size
ORDER BY ca.cohort_month, ca.month_index;


-- churned vs repeat customers (churned = single order, 90+ days ago)
WITH order_counts AS (
    SELECT
        customer_id,
        COUNT(*) AS num_orders,
        MAX(order_date) AS last_order_date
    FROM orders
    WHERE status = 'Completed'
    GROUP BY customer_id
)
SELECT
    CASE
        WHEN num_orders >= 2 THEN 'Repeat'
        WHEN num_orders = 1 AND
             julianday('now') - julianday(last_order_date) > 90 THEN 'Churned'
        ELSE 'New / Active (single order, recent)'
    END AS customer_status,
    COUNT(*) AS num_customers
FROM order_counts
GROUP BY customer_status;


-- customer segmentation: frequency tier + spend tier
WITH customer_stats AS (
    SELECT
        c.customer_id,
        c.name,
        COUNT(DISTINCT o.order_id) AS frequency,
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS monetary,
        julianday('now') - julianday(MAX(o.order_date)) AS recency_days
    FROM customers c
    JOIN orders o        ON c.customer_id = o.customer_id
    JOIN order_items oi  ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY c.customer_id, c.name
)
SELECT
    customer_id,
    name,
    frequency,
    monetary,
    ROUND(recency_days, 0) AS recency_days,
    CASE
        WHEN frequency = 1 THEN 'One-time'
        WHEN frequency BETWEEN 2 AND 4 THEN 'Occasional'
        ELSE 'Loyal'
    END AS frequency_segment,
    CASE
        WHEN monetary < 100 THEN 'Low'
        WHEN monetary BETWEEN 100 AND 500 THEN 'Medium'
        ELSE 'High'
    END AS spend_segment
FROM customer_stats
ORDER BY monetary DESC;
