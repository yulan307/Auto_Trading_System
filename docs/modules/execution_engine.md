# Execution Engine

## 目标

提供统一下单、撤单、订单查询接口，屏蔽 mock 与真实券商实现差异。

## 输入

- `OrderRequest`
- `order_id`

## 输出

- `OrderStatus`
- 订单与成交事件

## 核心逻辑

- 校验订单请求
- 路由到 broker
- 维护订单状态流转
- 回调账户更新

## 状态变量

- broker 类型
- `submitted` / `filled` / `canceled` / `rejected`
- 提交价格与成交价格

## 边界条件

- 数量小于等于 0
- `limit` 单缺少价格
- broker 异常
- 撤单时订单已成交

## MVP范围

- `mock broker`
- `market` / `limit`
- fee 与 slippage 先保留接口

## 测试方案

- 下单数量校验
- mock 下单成交测试
- 撤单测试
- 订单状态查询测试
