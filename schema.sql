
CREATE TABLE adm_areas (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    parent_id BIGINT NULL,
    area_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES adm_areas(id)
);

CREATE TABLE commodity_categories (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE commodities (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    unit VARCHAR(50),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE commodity_category_map (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    commodity_id BIGINT NOT NULL,
    category_id BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (commodity_id) REFERENCES commodities(id),
    FOREIGN KEY (category_id) REFERENCES commodity_categories(id),
    UNIQUE (commodity_id, category_id)
);

CREATE TABLE commodity_listings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    commodity_id BIGINT NOT NULL,
    adm_area_id BIGINT NOT NULL,
    title VARCHAR(200),
    description TEXT,
    price DECIMAL(12,2) NOT NULL,
    quantity DECIMAL(12,2),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (commodity_id) REFERENCES commodities(id),
    FOREIGN KEY (adm_area_id) REFERENCES adm_areas(id)
);

CREATE TABLE listings_images (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    listing_id BIGINT NOT NULL,
    image_url VARCHAR(255) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (listing_id) REFERENCES commodity_listings(id)
);

CREATE TABLE orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    listing_id BIGINT NOT NULL,
    quantity DECIMAL(12,2) NOT NULL,
    total_price DECIMAL(12,2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (listing_id) REFERENCES commodity_listings(id)
);
