DO $$

DECLARE
    v_film_id uuid := gen_random_uuid();
    v_genre_id uuid := '1cacff68-643e-4ddd-8f57-84b62538081a'; -- Драма
    v_actor_id uuid := gen_random_uuid();
    v_director_id uuid := gen_random_uuid();
BEGIN
    -- Вставка фильма
    INSERT INTO content.film_work (id, title, description, creation_date, rating, type, created, modified)
    VALUES (
        v_film_id,
        'Побег из Шоушенка',
        'Банкир Энди Дюфрейн ошибочно осужден за убийство и отправлен в тюрьму строгого режима.',
        '1994-09-23',
        9.3,
        'movie',
        NOW(),
        NOW()
    );
    
    -- Вставка персоны (актера)
    INSERT INTO content.person (id, full_name, created, modified)
    VALUES (v_actor_id, 'Тим Роббинс', NOW(), NOW());
    
    -- Вставка персоны (режиссера)
    INSERT INTO content.person (id, full_name, created, modified)
    VALUES (v_director_id, 'Фрэнк Дарабонт', NOW(), NOW());
    
    -- Связь с жанром
    INSERT INTO content.genre_film_work (id, genre_id, film_work_id, created)
    VALUES (gen_random_uuid(), v_genre_id, v_film_id, NOW());
    
    -- Связь с актером
    INSERT INTO content.person_film_work (id, person_id, film_work_id, role, created)
    VALUES (gen_random_uuid(), v_actor_id, v_film_id, 'actor', NOW());
    
    -- Связь с режиссером
    INSERT INTO content.person_film_work (id, person_id, film_work_id, role, created)
    VALUES (gen_random_uuid(), v_director_id, v_film_id, 'director', NOW());
END $$;


