-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 区域配置
CREATE TABLE IF NOT EXISTS config_area (
    config_id VARCHAR(50) PRIMARY KEY,
    parent_id VARCHAR(50),
    name VARCHAR(100),
    level INT,
    energy_type VARCHAR(20),
    park_id INT,
    is_delete INT DEFAULT 0
);

-- 项目配置
CREATE TABLE IF NOT EXISTS config_item (
    config_id VARCHAR(50) PRIMARY KEY,
    parent_id VARCHAR(50),
    name VARCHAR(100),
    level INT,
    energy_type VARCHAR(20),
    park_id INT,
    is_delete INT DEFAULT 0
);

-- 设备信息
CREATE TABLE IF NOT EXISTS device (
    device_id BIGINT PRIMARY KEY,
    device_no VARCHAR(50),
    device_name VARCHAR(200),
    point_type_id BIGINT,
    region_id BIGINT,
    building_id BIGINT,
    floor_id BIGINT,
    status INT DEFAULT 1,
    remark TEXT
);

-- 设备-配置关联
CREATE TABLE IF NOT EXISTS config_device (
    config_device_id BIGINT PRIMARY KEY,
    config_id VARCHAR(50),
    device_id BIGINT,
    device_level INT,
    energy_type VARCHAR(20),
    config_type VARCHAR(20)
);

-- 电力数据（时序表）
CREATE TABLE IF NOT EXISTS electric_data (
    time TIMESTAMPTZ NOT NULL,
    device_id BIGINT NOT NULL,
    point_id VARCHAR(50),
    value DOUBLE PRECISION,
    incr DOUBLE PRECISION
);

SELECT create_hypertable('electric_data', 'time', if_not_exists => TRUE);
SELECT add_retention_policy('electric_data', INTERVAL '30 days', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_electric_device ON electric_data (device_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_electric_point ON electric_data (point_id, time DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_electric_unique ON electric_data (time, point_id);

-- 告警表
CREATE TABLE IF NOT EXISTS alert (
    id BIGSERIAL PRIMARY KEY,
    device_id BIGINT,
    point_id VARCHAR(50),
    alert_type VARCHAR(20) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    message TEXT,
    value DOUBLE PRECISION,
    threshold DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alert_device ON alert (device_id);
CREATE INDEX IF NOT EXISTS idx_alert_point ON alert (point_id);
CREATE INDEX IF NOT EXISTS idx_alert_active ON alert (resolved_at) WHERE resolved_at IS NULL;

-- 阈值配置
CREATE TABLE IF NOT EXISTS threshold_config (
    id SERIAL PRIMARY KEY,
    device_id BIGINT,
    point_id VARCHAR(50),
    metric VARCHAR(20) DEFAULT 'incr',
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    severity VARCHAR(10) DEFAULT 'WARNING'
);

-- 设备特征（用于仿真）
CREATE TABLE IF NOT EXISTS device_profile (
    point_id VARCHAR(50) PRIMARY KEY,
    device_id BIGINT,
    display_name VARCHAR(100),
    device_type VARCHAR(20),
    area_name VARCHAR(50),
    mean_value DOUBLE PRECISION,
    std_value DOUBLE PRECISION,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    last_value DOUBLE PRECISION DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_profile_area ON device_profile (area_name);
CREATE INDEX IF NOT EXISTS idx_profile_type ON device_profile (device_type);
