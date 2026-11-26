-- Release Day Radar — relational schema (MySQL 8)
-- One central table (films) and four tables that point to it with film_id.
-- Run order matters: films first, because the others have FOREIGN KEYs to it.

DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS trends_daily;
DROP TABLE IF EXISTS box_office;
DROP TABLE IF EXISTS trailers;
DROP TABLE IF EXISTS films;

-- One row per film. film_id is our own canonical key (built in step 05),
-- because each source spells titles differently ("Kantara - A Legend: Chapter 1" on TMDb).
CREATE TABLE films (
    film_id       VARCHAR(40)  NOT NULL PRIMARY KEY,
    title_clean   VARCHAR(120) NOT NULL,
    language      VARCHAR(20)  NOT NULL,          -- nominal: Hindi / Kannada / Malayalam / Telugu
    genre         VARCHAR(120),                   -- nominal, comma-separated TMDb genres
    runtime_min   SMALLINT,                       -- discrete
    release_date  DATE         NOT NULL,
    budget_cr     DECIMAL(8,2),                   -- continuous, ₹ crore, NULL when not published
    tmdb_id       INT          UNIQUE
);

-- One row per trailer VIDEO. A film can have several (dubbed language versions).
CREATE TABLE trailers (
    trailer_id        INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    film_id           VARCHAR(40)  NOT NULL,
    youtube_video_id  CHAR(11)     NOT NULL UNIQUE,
    is_main_trailer   BOOLEAN      NOT NULL,
    publish_ts        DATETIME     NOT NULL,      -- stored in IST
    views             BIGINT       NOT NULL,      -- discrete count
    likes             BIGINT,                     -- NULL if the channel hides likes
    comment_count     INT,
    FOREIGN KEY (film_id) REFERENCES films(film_id)
);

-- Long ("tidy") format: one row per film per metric, so new metrics need no new columns.
CREATE TABLE box_office (
    film_id    VARCHAR(40)  NOT NULL,
    metric     VARCHAR(40)  NOT NULL,             -- e.g. first_weekend_ww, first_weekend_per_day, lifetime_gross_ww
    value_cr   DECIMAL(10,2) NOT NULL,            -- ₹ crore
    source     VARCHAR(60)  NOT NULL,             -- which page/table it came from
    note       VARCHAR(200),                      -- e.g. "range midpoint", "domestic only", "converted from USD"
    PRIMARY KEY (film_id, metric, source),
    FOREIGN KEY (film_id) REFERENCES films(film_id)
);

-- Comments on each film's main trailer. NO usernames or channel ids (privacy rule).
CREATE TABLE comments (
    comment_id      VARCHAR(64)  NOT NULL PRIMARY KEY,
    film_id         VARCHAR(40)  NOT NULL,
    published_ts    DATETIME     NOT NULL,        -- IST
    text_clean      TEXT         NOT NULL,
    length          INT          NOT NULL,        -- characters, discrete
    vader_compound  DECIMAL(5,4),                 -- continuous, -1 to +1
    FOREIGN KEY (film_id) REFERENCES films(film_id),
    INDEX idx_comments_film_time (film_id, published_ts)
);

-- Google Trends: one row per film per day.
CREATE TABLE trends_daily (
    film_id   VARCHAR(40) NOT NULL,
    date      DATE        NOT NULL,
    interest  DECIMAL(5,1) NOT NULL,              -- 0–100, relative within each film's own export
    PRIMARY KEY (film_id, date),
    FOREIGN KEY (film_id) REFERENCES films(film_id)
);
