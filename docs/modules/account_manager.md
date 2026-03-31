# Account Manager

## 目标

统一账户读取与更新接口，在回测和 paper 模式下使用虚拟账户，在 live 模式下预留真实券商账户接口。

## 输入

- `ticker`
- `trade_record`
- `as_of_date`

## 输出

- `AccountSnapshot`
- `Position | None`
- 最近交易统计字典

## 核心逻辑

- 读取账户快照
- 读取单个持仓
- 汇总最近 5 日与本周交易统计
- 应用成交记录更新账户

## 状态变量

- `account.db`
- `account_snapshots`
- `positions`
- `trade_records`
- `orders`

## 边界条件

- 账户初始化缺失
- 卖出超过持仓
- 交易记录不完整
- 快照与持仓不同步

## MVP范围

- 本地虚拟账户
- 单账户
- 现金账户

## 测试方案

- 初始资金重置测试
- 买入更新现金与持仓测试
- 同标的重复买入均价更新测试
