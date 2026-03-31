# Logging System

## 目标

记录系统关键事件，支持调试、审计、回测解释和线上排障。

## 输入

- `level`
- `module`
- `event_type`
- `message`
- `ticker`
- `payload`

## 输出

- 文件日志
- SQLite 日志事件表

## 核心逻辑

- 统一格式化日志
- 写入 `app.log` / `trade.log` / `decision.log` / `error.log`
- 同步写入 `logs.db`

## 状态变量

- `logs/`
- `logs.db`
- `log_events`

## 边界条件

- 不支持的日志级别
- payload 序列化失败
- 日志目录或数据库不可写

## MVP范围

- 文件日志
- SQLite 事件存储
- 关键事件类型固定枚举

## 测试方案

- 日志文件创建测试
- 数据库事件写入测试
- 日志分流测试
