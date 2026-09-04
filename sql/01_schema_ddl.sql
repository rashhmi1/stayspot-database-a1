
CREATE TABLE guests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    wallet_balance DECIMAL(10,2) NOT NULL CHECK (wallet_balance >= 0.00)
);

CREATE TABLE wallet_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id UUID NOT NULL REFERENCES guests(id),
    amount_changed DECIMAL(10,2) NOT NULL,
    action_type VARCHAR(10) NOT NULL CHECK (action_type IN ('DEBIT', 'CREDIT')),
    balance_after DECIMAL(10,2) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    base_price DECIMAL(10,2) NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL
);

CREATE TABLE bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id UUID NOT NULL REFERENCES guests(id),
    property_id UUID NOT NULL REFERENCES properties(id),
    total_cost DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('CONFIRMED', 'CHECKED IN', 'COMPLETED')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
