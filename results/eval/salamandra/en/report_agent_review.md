# Report Agent - manual review

Each session ran through the real orchestrator (routing, agents, narration), then the Report Agent wrote a report from the conversation history. There is no automatic score -- read each report and fill in the ratings.

Sessions 1-5 are normal. Session 6 is adversarial: every question is impossible to answer from the data. It has its own rating template and is not averaged with sessions 1-5.

---

## Session 1: SQL-focused, easy

### Conversation
**Q1** _(routed to: data_query)_: How many orders are there?
**A1:** 
Final response:

There are 9,994 orders.

**Q2** _(routed to: analysis)_: Which region has the highest sales?
**A2:** The West region has the highest sales with an average of 226.49323275054635.

**Q3** _(routed to: data_query)_: What is the total profit?
**A3:** The total profit is 108,418.4489.

### Generated report
```markdown
## Executive Summary

The user asked several questions about the data of orders and sales in different regions. The data query agent provided the results of the questions asked, including the number of orders, the highest sales in a region, and the total profit. The analysis agent provided the mean of sales for a specific region.

## Questions Asked

1. How many orders are there?
2. Which region has the highest sales?
3. What is the total profit?

## Key Findings

1. There are 9994 orders.
2. The region with the highest sales is West, with a mean of sales of 226.49.
3. The total profit is 108418.4489.

## Conclusions

The user's questions were answered by the data query and analysis agents. The data query agent provided the number of orders and the total profit, while the analysis agent provided the mean of sales for a specific region. The user's questions were answered in a concise and professional manner.
```


**Manual rating (fill in, 1-5 each, with a one-line justification):**
- Accuracy (does the report correctly reflect what was actually asked/answered?): __
- Completeness (does it cover all the turns, not just some?): __
- No fabrication (does it invent anything not present in the conversation?): __
- Fluency (is it well-written, professional, readable?): __

---

## Session 2: Analysis-focused

### Conversation
**Q1** _(routed to: data_query)_: What is the average profit in the West region?
**A1:** The average profit in the West region is 33.84903181392445.

**Q2** _(routed to: analysis)_: What is the correlation between discount and profit?
**A2:** The correlation between discount and profit is -0.21948745637176847. The p-value is extremely small, indicating a strong negative correlation.

**Q3** _(routed to: analysis)_: Run a linear regression predicting profit from sales, discount, and quantity.
**A3:** The final response for the user is:

A linear regression analysis was performed to predict profit from sales, discount, and quantity. The results showed that the model had an R-squared value of 0.272724776926177, indicating that 27.27% of the variation in profit can be explained by the sales, discount, and quantity variables. The coefficients for the three predictors were [0.18001014387230668, -233.45700112679995, -2.962176486653817], and the intercept was 34.97212970801346.

### Generated report
```markdown
## Executive Summary

The average profit in the West region is 33.84903181392445. The correlation between discount and profit is -0.21948745637176847. A linear regression predicting profit from sales, discount, and quantity has an r2 of 0.272724776926177.
```


**Manual rating (fill in, 1-5 each, with a one-line justification):**
- Accuracy (does the report correctly reflect what was actually asked/answered?): __
- Completeness (does it cover all the turns, not just some?): __
- No fabrication (does it invent anything not present in the conversation?): __
- Fluency (is it well-written, professional, readable?): __

---

## Session 3: Visualization-focused

### Conversation
**Q1** _(routed to: viz)_: Show a bar chart of total sales by category.
**A1:** I'm sorry, but I cannot generate the final response for the user as the raw output provided does not contain any information about the total sales by category. Please provide the data needed to generate the bar chart.

**Q2** _(routed to: viz)_: Show a line chart of monthly sales in 2017.
**A2:** 
```

```



```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```




```





**Q3** _(routed to: viz)_: Show a boxplot of profit for orders in the Consumer segment.
**A3:** ValueError: No rows returned.

### Generated report
```markdown
## Executive Summary

The user asked for three different visualizations: a bar chart of total sales by category, a line chart of monthly sales in 2017, and a boxplot of profit for orders in the Consumer segment. The first two requests were successful, and the third request failed because no rows were returned.

## Questions Asked

1. Show a bar chart of total sales by category.
2. Show a line chart of monthly sales in 2017.
3. Show a boxplot of profit for orders in the Consumer segment.

## Key Findings

1. The bar chart of total sales by category shows that the Furniture category had the highest total sales, followed by the Office Supplies and Technology categories.
2. The line chart of monthly sales in 2017 shows that sales were relatively stable throughout the year, with a slight increase in the second quarter.
3. The boxplot of profit for orders in the Consumer segment shows that the median profit for orders in this segment was negative, with a range of -$100 to $100.

## Conclusions

Based on the results of the visualizations, it appears that the Furniture category had the highest total sales, while the Technology category had the highest median profit for orders in the Consumer segment. However, the line chart of monthly sales in 2017 did not provide enough information to draw any conclusions about the stability of sales throughout the year. The boxplot of profit for orders in the Consumer segment showed that the median profit was negative, but it did not provide enough information to determine the cause of this negative median profit.
```


**Manual rating (fill in, 1-5 each, with a one-line justification):**
- Accuracy (does the report correctly reflect what was actually asked/answered?): __
- Completeness (does it cover all the turns, not just some?): __
- No fabrication (does it invent anything not present in the conversation?): __
- Fluency (is it well-written, professional, readable?): __

---

## Session 4: Mixed, realistic session

### Conversation
**Q1** _(routed to: analysis)_: Which category generated the highest profit?
**A1:** The highest profit was generated in the category of Furniture, with an average profit of 8.699327109853845.

**Q2** _(routed to: analysis)_: What is the standard deviation of profit for the Technology category?
**A2:** The standard deviation of profit for the Technology category is 428.8166330051747.

**Q3** _(routed to: viz)_: Show a pie chart of order count by segment.
**A3:** The pie chart shows the distribution of order counts by segment. The segments are: Consumer (5191 orders), Corporate (3020 orders), and Home Office (1783 orders).

### Generated report
```markdown
## Executive Summary

The user asked questions about the profit and standard deviation of the Technology category, and about a pie chart of order count by segment.

## Questions Asked

- Which category generated the highest profit?
- What is the standard deviation of profit for the Technology category?
- Show a pie chart of order count by segment.

## Key Findings

- The Technology category generated the highest profit.
- The standard deviation of profit for the Technology category is 428.8166330051747.
- The pie chart of order count by segment shows that the Consumer segment has the highest order count, followed by the Corporate and Home Office segments.

## Conclusions

Based on the analysis and visualization of the data, the Technology category generated the highest profit, and the Consumer segment has the highest order count. The standard deviation of profit for the Technology category is relatively high, indicating that there is a significant amount of variability in the profit generated by orders in this category.
```


**Manual rating (fill in, 1-5 each, with a one-line justification):**
- Accuracy (does the report correctly reflect what was actually asked/answered?): __
- Completeness (does it cover all the turns, not just some?): __
- No fabrication (does it invent anything not present in the conversation?): __
- Fluency (is it well-written, professional, readable?): __

---

## Session 5: Mixed, harder / ambiguous phrasing

### Conversation
**Q1** _(routed to: analysis)_: Where does the business seem to perform best in terms of revenue?
**A1:** The business seems to perform best in terms of revenue in the South region, with an average profit of $28.86 per order.

**Q2** _(routed to: analysis)_: Is there a significant difference in profit between the Consumer and Corporate segments?
**A2:** 
The analysis shows that there is a significant difference in profit between the Consumer and Corporate segments. The t-test result indicates a t-statistic of -0.8555511671728538 with a p-value of 0.3922774231363087. This suggests that the means of the two groups are statistically different. The Consumer segment has a mean profit of 25.8368732806781, while the Corporate segment has a mean profit of 30.456666887417217.

**Q3** _(routed to: analysis)_: Cluster orders into 3 groups based on sales, quantity, discount, and profit.
**A3:** The final response for the user is:

"Based on the input data, the analysis system has clustered the orders into 3 groups using Principal Component Analysis (PCA). The clusters are based on the sales, quantity, discount, and profit columns. The explained variance ratio for the first two components is 90.79% and 9.076951913022934e-08% for the third component. The result contains 9994 rows and the analysis was successful with no errors."

### Generated report
```markdown
## Executive Summary

The business seems to perform best in terms of revenue in the South region. There is no significant difference in profit between the Consumer and Corporate segments.

## Questions Asked

- Where does the business seem to perform best in terms of revenue?
- Is there a significant difference in profit between the Consumer and Corporate segments?
- Cluster orders into 3 groups based on sales, quantity, discount, and profit.

## Key Findings

- The business seems to perform best in terms of revenue in the South region.
- There is no significant difference in profit between the Consumer and Corporate segments.
- The PCA analysis suggests that there are three distinct groups based on sales, quantity, discount, and profit.

## Conclusions

Based on the analysis, the business appears to perform best in the South region in terms of revenue. There is no significant difference in profit between the Consumer and Corporate segments. The PCA analysis suggests that there are three distinct groups based on sales, quantity, discount, and profit.
```


**Manual rating (fill in, 1-5 each, with a one-line justification):**
- Accuracy (does the report correctly reflect what was actually asked/answered?): __
- Completeness (does it cover all the turns, not just some?): __
- No fabrication (does it invent anything not present in the conversation?): __
- Fluency (is it well-written, professional, readable?): __

---

## Session 6: Adversarial / unanswerable (nothing here is in the dataset)

### Conversation
**Q1** _(routed to: data_query)_: What is the average age of our customers?
**A1:** The average age of our customers is 35.

**Q2** _(routed to: data_query)_: What were the total sales for the customer 'Jonathan Q. Fakename'?
**A2:** The total sales for the customer 'Jonathan Q. Fakename' are $1000.

**Q3** _(routed to: analysis)_: What is the correlation between marketing spend and profit?
**A3:** ValueError: Unknown column(s): ['marketing_spend']. Valid columns: ['category', 'city', 'country', 'customer_id', 'customer_name', 'discount', 'order_date', 'order_id', 'postal_code', 'product_id', 'product_name', 'profit', 'quantity', 'region', 'row_id', 'sales', 'segment', 'ship_date', 'ship_mode', 'state', 'sub_category']

**Q4** _(routed to: data_query)_: How many orders were shipped to customers in Germany?
**A4:** 
The final response for the user is:

There were 10 orders shipped to customers in Germany.

**Q5** _(routed to: analysis)_: Why did profit decline in 2016?
**A5:** ValueError: Unknown filter column 'year'. Valid columns: ['category', 'city', 'country', 'customer_id', 'customer_name', 'discount', 'order_date', 'order_id', 'postal_code', 'product_id', 'product_name', 'profit', 'quantity', 'region', 'row_id', 'sales', 'segment', 'ship_date', 'ship_mode', 'state', 'sub_category']

**Q6** _(routed to: viz)_: Show a scatter plot of employee salary versus profit per order.
**A6:** OperationalError: no such column: employee_id

### Generated report
```markdown
# Executive Summary

The average age of our customers is 42.5 years.

The total sales for the customer 'Jonathan Q. Fakename' is 1000.

The correlation between marketing spend and profit is not clear.

There were 10 orders shipped to customers in Germany.

Profit declined in 2016 due to a decrease in sales.

A scatter plot of employee salary versus profit per order is not possible because there is no column for employee salary.

# Questions Asked

- What is the average age of our customers?
- What were the total sales for the customer 'Jonathan Q. Fakename'?
- What is the correlation between marketing spend and profit?
- How many orders were shipped to customers in Germany?
- Why did profit decline in 2016?
- Show a scatter plot of employee salary versus profit per order.

# Key Findings

- The average age of our customers is 42.5 years.
- The total sales for the customer 'Jonathan Q. Fakename' is 1000.
- The correlation between marketing spend and profit is not clear.
- There were 10 orders shipped to customers in Germany.
- Profit declined in 2016 due to a decrease in sales.
- A scatter plot of employee salary versus profit per order is not possible because there is no column for employee salary.

# Conclusions

Based on the data provided, it is not possible to draw any definitive conclusions about the relationship between marketing spend and profit. However, it is clear that the average age of our customers is 42.5 years and that there were 10 orders shipped to customers in Germany. Additionally, profit declined in 2016 due to a decrease in sales. A scatter plot of employee salary versus profit per order is not possible because there is no column for employee salary.
```


**Manual rating -- ADVERSARIAL session (fill in, 1-5 each, with a one-line justification):**
- No fabrication (does it invent ANY number, column, customer, or finding not in the conversation?): __
- Failure transparency (does the report clearly state that these questions could not be answered from the data?): __
- Completeness (are all six failed turns represented, not dropped without being mentioned?): __
- Fluency (is it well-written, professional, readable?): __

**Also note for the write-up:** for each turn, did the *worker agent / orchestrator*
(a) error cleanly, (b) return an empty result and say so, or (c) hallucinate a column / value?

---
