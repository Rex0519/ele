# 用电分析工具增强设计

## 问题

用户问"昨天照明用电哪个区域最高，比前天高多少？是哪里的差异"时，系统无法回答。

原因：现有 `compare_usage` 不支持按设备类型筛选，不支持指定日期对比。

## 改动

### A. 增强 compare_usage

新增参数：
- `device_type`（string, 可选）：设备类型筛选
- `date`（string, 可选，YYYY-MM-DD）：对比基准日，默认今天

### B. 新增 usage_ranking

按区域或设备类型维度统计用电排名。

参数：
- `dimension`（enum: area/device_type，必填）：聚合维度
- `device_type`（string, 可选）：设备类型筛选
- `area`（string, 可选）：区域名筛选
- `date`（string, 可选，YYYY-MM-DD）：统计日期，默认今天

### C. 更新 Dify system prompt

补充新工具用法说明。
