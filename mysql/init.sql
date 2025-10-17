SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS memodb
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE memodb;

CREATE TABLE IF NOT EXISTS users (
  id VARCHAR(36) PRIMARY KEY,
  username VARCHAR(255) UNIQUE,
  password TEXT
) CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS memos (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36),
  body TEXT,
  visibility ENUM('public','private','secret') NOT NULL,
  password TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

ALTER TABLE memos ADD FULLTEXT INDEX ft_memos_body (body) WITH PARSER ngram;

CREATE TABLE IF NOT EXISTS tags (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  UNIQUE KEY uniq_name (name)
) CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS memo_tags (
  memo_id VARCHAR(36) NOT NULL,
  tag_id INT NOT NULL,
  PRIMARY KEY (memo_id, tag_id),
  FOREIGN KEY (memo_id) REFERENCES memos(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
) CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

INSERT IGNORE INTO users (id, username, password) VALUES
('dummy_admin_id', 'admin', 'dummy_admin_pass');
INSERT IGNORE INTO users (id, username, password) VALUES
('dummy_super_admin_id', 'super-admin', 'dummy_super_admin_pass');
INSERT IGNORE INTO users (id, username, password) VALUES
('dummy_guest_id', 'guest', 'guest');

INSERT IGNORE INTO memos (id, user_id, body, visibility) VALUES
('dummy_admin_memo_id1', 'dummy_admin_id', '緊急でこのパスコードを社長に伝える必要があります。: flag{dummy_flag1}', 'private');
INSERT IGNORE INTO tags (name) VALUES ('urgent');
INSERT IGNORE INTO memo_tags (memo_id, tag_id)
VALUES ('dummy_admin_memo_id1', (SELECT id FROM tags WHERE name='urgent'));

INSERT IGNORE INTO memos (id, user_id, body, visibility) VALUES
('dummy_admin_memo_id2', 'dummy_admin_id', '私の社用PCのパスワード: flag{dummy_flag3}', 'private');
INSERT IGNORE INTO memos (id, user_id, body, visibility, password) VALUES
('dummy_admin_memo_id3', 'dummy_admin_id', '今年度の目標: flag{dummy_flag5}', 'secret', 'dummy_admin_memo_pass1');

INSERT IGNORE INTO memos (id, user_id, body, visibility, password) VALUES
('dummy_super_admin_memo_id1', 'dummy_super_admin_id', '合言葉: flag{dummy_flag6}', 'secret', 'dummy_super_admin_memo_pass1');