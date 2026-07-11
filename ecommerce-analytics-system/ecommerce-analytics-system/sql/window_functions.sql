-- window functions and ctes: rank, running total, moving average, growth rate

-- rank customers by lifetime value
WITH customer_ltv AS (
    SELECT
        c.customer_id,
        c.name,
        ROUND(SUM(oi.quantity * oi.unit_price), 2) AS lifetime_value
    FROM customers c
    JOIN orders o        ON c.customer_id = o.customer_id
    JOIN order_items oi  ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY c.customer_id, c.name
)
SELECT
    customer_id,
    name,
    lifetime_value,
    RANK()       OVER (ORDER BY lifetime_value DESC) AS ltv_rank,
    DENSE_RANK() OVER (ORDER BY lifetime_value DESC) AS ltv_dense_rank
FROM customer_ltv
ORDER BY lifetime_value DESC
LIMIT 20;


-- running total of monthly revenue
WITH monthly_revenue AS (
    SELECT
        strftime('%Y-%m', o.order_date) AS order_month,
        SUM(oi.quantity * oi.unit_price) AS monthly_total
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY order_month
)
SELECT
    order_month,
    ROUND(monthly_total, 2) AS monthly_total,
    ROUND(SUM(monthly_total) OVER (ORDER BY order_month), 2) AS running_total
FROM monthly_revenue
ORDER BY order_month;


-- 3-month moving average of monthly revenue
WITH monthly_revenue AS (
    SELECT
        strftime('%Y-%m', o.order_date) AS order_month,
        SUM(oi.quantity * oi.unit_price) AS monthly_total
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY order_month
)
SELECT
    order_month,
    ROUND(monthly_total, 2) AS monthly_total,
    ROUND(
        AVG(monthly_total) OVER (
            ORDER BY order_month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 2
    ) AS moving_avg_3month
FROM monthly_revenue
ORDER BY order_month;


-- monthly revenue -> month-over-month growth rate
WITH monthly_revenue AS (
    SELECT
        strftime('%Y-%m', o.order_date) AS order_month,
        SUM(oi.quantity * oi.unit_price) AS monthly_total
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY order_month
),
with_previous AS (
    SELECT
        order_month,
        monthly_total,
        LAG(monthly_total) OVER (ORDER BY order_month) AS prev_month_total
    FROM monthly_revenue
)
SELECT
    order_month,
    ROUND(monthly_total, 2) AS monthly_total,
    ROUND(prev_month_total, 2) AS prev_month_total,
    CASE
        WHEN prev_month_total IS NULL OR prev_month_total = 0 THEN NULL
        ELSE ROUND(100.0 * (monthly_total - prev_month_total) / prev_month_total, 2)
    END AS growth_rate_pct
FROM with_previous
ORDER BY order_month;


-- each customer's orders ranked by spend within their own history
WITH order_totals AS (
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        SUM(oi.quantity * oi.unit_price) AS order_total
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.status = 'Completed'
    GROUP BY o.order_id, o.customer_id, o.order_date
)
SELECT
    customer_id,
    order_id,
    order_date,
    ROUND(order_total, 2) AS order_total,
    RANK() OVER (PARTITION BY customer_id ORDER BY order_total DESC) AS rank_within_customer
FROM order_totals
ORDER BY customer_id, rank_within_customer
LIMIT 30;
