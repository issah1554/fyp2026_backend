from secrets import choice


PUBLIC_ID_ALPHABET = "123456789BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz"
PUBLIC_ID_LENGTH = 10
MAX_CONSECUTIVE_LETTERS = 3


def generate_public_id():
    public_id = []
    consecutive_letters = 0
    previous_was_letter = False

    for _index in range(PUBLIC_ID_LENGTH):
        while True:
            character = choice(PUBLIC_ID_ALPHABET)
            is_letter = character.isalpha()
            next_run = (
                consecutive_letters + 1
                if is_letter and previous_was_letter
                else 1
                if is_letter
                else 0
            )

            if next_run <= MAX_CONSECUTIVE_LETTERS:
                break

        public_id.append(character)
        consecutive_letters = next_run
        previous_was_letter = is_letter

    return "".join(public_id)


def generate_unique_public_id(model_class, field_name="public_id"):
    while True:
        public_id = generate_public_id()
        if not model_class.objects.filter(**{field_name: public_id}).exists():
            return public_id
