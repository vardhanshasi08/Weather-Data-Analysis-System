CREATE DATABASE IF NOT EXISTS weather_analysis;
USE weather_analysis;

CREATE TABLE IF NOT EXISTS weather_records (
    record_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    observation_date DATE NOT NULL,
    location VARCHAR(120) NOT NULL,
    temperature DOUBLE NOT NULL COMMENT 'Degrees Celsius',
    humidity DOUBLE NOT NULL COMMENT 'Percent, 0 to 100',
    rainfall DOUBLE NOT NULL COMMENT 'Millimetres, >= 0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_weather_date_location (observation_date, location),
    INDEX idx_weather_date (observation_date),
    INDEX idx_weather_location (location)
);
