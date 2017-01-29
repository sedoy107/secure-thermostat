-- phpMyAdmin SQL Dump
-- version 3.4.11.1deb2+deb7u6
-- http://www.phpmyadmin.net
--
-- Host: localhost
-- Generation Time: Jan 21, 2017 at 11:04 AM
-- Server version: 5.5.53
-- PHP Version: 5.4.45-0+deb7u6

SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;

--
-- Database: `thermostat`
--

-- --------------------------------------------------------

--
-- Table structure for table `clients_history`
--

CREATE TABLE IF NOT EXISTS `clients_history` (
  `entry_id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(100) NOT NULL,
  `timestamp` datetime NOT NULL,
  `session_end_date` datetime NOT NULL,
  `obj` text NOT NULL,
  PRIMARY KEY (`entry_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii AUTO_INCREMENT=1 ;

-- --------------------------------------------------------

--
-- Table structure for table `current_clients`
--

CREATE TABLE IF NOT EXISTS `current_clients` (
  `auth_id` int(11) unsigned NOT NULL,
  `username` varchar(100) NOT NULL,
  `activity_tstamp` datetime NOT NULL,
  `login_tstamp` datetime NOT NULL,
  `obj` text NOT NULL,
  PRIMARY KEY (`auth_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

-- --------------------------------------------------------

--
-- Table structure for table `current_hvacs`
--

CREATE TABLE IF NOT EXISTS `current_hvacs` (
  `hvac_id` varchar(106) NOT NULL,
  `host` varchar(100) NOT NULL,
  `port` smallint(6) NOT NULL,
  `timestamp` datetime NOT NULL,
  `start_time` datetime NOT NULL,
  `sensor_id` varchar(250) NOT NULL,
  `fan` tinyint(1) NOT NULL,
  `heat` tinyint(1) NOT NULL,
  `cool` tinyint(1) NOT NULL,
  `delta` float NOT NULL,
  `h_timeout_key` int(11) NOT NULL DEFAULT '0',
  `c_timeout_key` int(11) NOT NULL DEFAULT '0',
  `obj` text NOT NULL,
  PRIMARY KEY (`hvac_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

-- --------------------------------------------------------

--
-- Table structure for table `current_sensors`
--

CREATE TABLE IF NOT EXISTS `current_sensors` (
  `sensor_id` varchar(250) NOT NULL,
  `status` int(11) NOT NULL,
  `priority` int(11) NOT NULL,
  `timestamp` datetime NOT NULL,
  `start_time` datetime NOT NULL,
  `raw_data` text CHARACTER SET ascii COLLATE ascii_bin,
  `obj` text NOT NULL,
  PRIMARY KEY (`sensor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

-- --------------------------------------------------------

--
-- Table structure for table `hvacs`
--

CREATE TABLE IF NOT EXISTS `hvacs` (
  `hvac_id` varchar(106) NOT NULL,
  `host` varchar(100) NOT NULL,
  `port` smallint(6) NOT NULL,
  `username` varchar(100) NOT NULL,
  `password` varchar(100) DEFAULT NULL,
  `path` varchar(128) NOT NULL,
  `protocol` varchar(8) NOT NULL DEFAULT 'sshrpc',
  `cool_wattage` int(11) NOT NULL,
  `heat_wattage` int(11) NOT NULL,
  `cool_kwph` float NOT NULL,
  `heat_kwph` float NOT NULL,
  `cool_usage` text,
  `heat_usage` text,
  `description` text NOT NULL,
  `obj` text NOT NULL,
  PRIMARY KEY (`hvac_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

-- --------------------------------------------------------

--
-- Table structure for table `hvacs_history`
--

CREATE TABLE IF NOT EXISTS `hvacs_history` (
  `entry_id` int(11) NOT NULL AUTO_INCREMENT,
  `hvac` text NOT NULL,
  `timestamp` datetime NOT NULL,
  `obj` text NOT NULL,
  PRIMARY KEY (`entry_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii AUTO_INCREMENT=1 ;

-- --------------------------------------------------------

--
-- Table structure for table `hvac_jobs`
--

CREATE TABLE IF NOT EXISTS `hvac_jobs` (
  `job_id` int(11) NOT NULL AUTO_INCREMENT,
  `job_type` varchar(32) NOT NULL,
  `status` varchar(32) NOT NULL,
  `auth_id` int(11) unsigned NOT NULL COMMENT 'publisher_name = username',
  `publisher` varchar(100) NOT NULL,
  `start_time` datetime NOT NULL,
  `timestamp` datetime NOT NULL,
  `period` int(11) NOT NULL,
  `hvac_id` varchar(106) NOT NULL,
  `hvac_fan` varchar(32) NOT NULL,
  `hvac_mode` varchar(32) NOT NULL,
  `hvac_temp` int(11) NOT NULL,
  `hvac_delta` tinyint(1) NOT NULL,
  `obj` text NOT NULL,
  PRIMARY KEY (`job_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii AUTO_INCREMENT=1 ;

-- --------------------------------------------------------

--
-- Table structure for table `hvac_job_history`
--

CREATE TABLE IF NOT EXISTS `hvac_job_history` (
  `job_id` int(11) NOT NULL,
  `job_type` varchar(32) NOT NULL,
  `publisher` varchar(100) NOT NULL,
  `start_time` datetime NOT NULL,
  `end_time` datetime NOT NULL,
  `period` int(11) NOT NULL,
  `hvac_fan` tinyint(1) NOT NULL,
  `hvac_mode` tinyint(1) NOT NULL,
  `hvac_temp` int(11) NOT NULL,
  `hvac_delta` tinyint(1) NOT NULL,
  `obj` text NOT NULL,
  PRIMARY KEY (`job_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

-- --------------------------------------------------------

--
-- Table structure for table `sensors`
--

CREATE TABLE IF NOT EXISTS `sensors` (
  `sensor_id` varchar(250) NOT NULL DEFAULT '' COMMENT 'sum of host, port, stype, and path',
  `stype` varchar(16) NOT NULL,
  `host` varchar(100) NOT NULL,
  `port` smallint(6) NOT NULL,
  `username` varchar(100) NOT NULL,
  `password` varchar(100) DEFAULT NULL,
  `path` varchar(128) NOT NULL,
  `protocol` varchar(8) NOT NULL,
  `obj` text NOT NULL,
  PRIMARY KEY (`sensor_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

-- --------------------------------------------------------

--
-- Table structure for table `sensors_history`
--

CREATE TABLE IF NOT EXISTS `sensors_history` (
  `entry_id` int(11) NOT NULL AUTO_INCREMENT,
  `sensor` text NOT NULL,
  `timestamp` datetime NOT NULL,
  `obj` text NOT NULL,
  PRIMARY KEY (`entry_id`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii AUTO_INCREMENT=1 ;

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE IF NOT EXISTS `users` (
  `salt` varchar(100) NOT NULL,
  `username` varchar(100) NOT NULL,
  `pass_hash` varchar(128) NOT NULL,
  `timestamp` datetime NOT NULL,
  `obj` text NOT NULL,
  PRIMARY KEY (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=ascii;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
