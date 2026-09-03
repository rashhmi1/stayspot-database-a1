CREATE OR REPLACE PROCEDURE sp_execute_booking(
    p_guest_id UUID,
    p_property_id UUID,
    p_total_cost DECIMAL(10,2)
)
LANGUAGE plpgsql
AS $$
BEGIN

    UPDATE guests
    SET wallet_balance = wallet_balance - p_total_cost
    WHERE id = p_guest_id;

    INSERT INTO bookings
        (guest_id, property_id, total_cost, status, created_at)
    VALUES
        (p_guest_id, p_property_id, p_total_cost, 'CONFIRMED', NOW());

EXCEPTION
    WHEN check_violation THEN
        RAISE NOTICE
            'Insufficient funds or constraint violation for guest %',
            p_guest_id;

    WHEN OTHERS THEN
        RAISE NOTICE
            'Transaction failed: %',
            SQLERRM;
END;
$$;