-- DROP TABLE IF EXISTS Auth_Token;
-- DROP TABLE IF EXISTS Data;
-- DROP TABLE IF EXISTS DeviceOwners;
-- DROP TABLE IF EXISTS Device;
-- DROP TABLE IF EXISTS Users;
-- DROP TABLE IF EXISTS Obstacles;

CREATE TABLE IF NOT EXISTS Device (
    `device-id` varchar(255) NOT NULL PRIMARY KEY,
    `name` varchar(255) NOT NULL,
    `password` varchar(255) NOT NULL,
    `status` varchar(255) NOT NULL DEFAULT 'public',
    `description` varchar(500) DEFAULT NULL,
    `lora-dev-eui` varchar(255) DEFAULT NULL
)ENGINE=InnoDB DEFAULT CHARSET=utf8;


CREATE TABLE IF NOT EXISTS Users (
    `username` varchar(255) PRIMARY KEY NOT NULL,
    `password` varchar(255) NOT NULL,
    `email` varchar(255),
    `role` varchar(255) NOT NULL DEFAULT 'user',
    `api-key` varchar(255)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8;


CREATE TABLE IF NOT EXISTS DeviceOwners (
    `id` serial,
    `owner` varchar(255) NOT NULL,
    `device` varchar(255) NOT NULL,
    `super-owner` tinyint(1) NOT NULL DEFAULT 0,
    FOREIGN KEY (`owner`) REFERENCES Users(`username`),
    FOREIGN KEY (`device`) REFERENCES Device(`device-id`)
)ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Auth_Token (
    `token` varchar(255) PRIMARY KEY,
    `user` varchar(255) NOT NULL,
    `date-exp` DATETIME(3) NOT NULL,
    FOREIGN KEY (`user`) REFERENCES Users(`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Objets (
    `ìd` serial,
    `timestamp` DATETIME(3) NOT NULL,
    `eui` varchar(255) NOT NULL,
    `latitude` float NOT NULL,
    `longitude` float NOT NULL,
    `label` varchar(255) NOT NULL,
    FOREIGN KEY (`eui`) REFERENCES Device (`device-id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;




INSERT INTO Users (username, password, role) VALUES ('a', '$2b$12$MF83CvvYYxd6QSOb4SPm4.m4PXghwwRncpURAro7sfs2AAkZ6ORuW', 'admin');

