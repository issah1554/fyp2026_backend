from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.auth.models import Profile
from apps.users.models import Role


SAMPLE_USERS = [
    {
        "username": "admin_sample",
        "email": "system.admin@user.com",
        "first_name": "System",
        "last_name": "Admin",
        "role": Profile.Role.ADMIN,
        "phone_number": "+255700000001",
        "organization": "DIT FYP Admin",
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "username": "farmer_sample",
        "email": "system.farmer@user.com",
        "first_name": "Asha",
        "last_name": "Farmer",
        "role": Profile.Role.FARMER,
        "phone_number": "+255700000002",
        "organization": "Morogoro Farmers Cooperative",
    },
    {
        "username": "entrepreneur_sample",
        "email": "system.entrepreneur@user.com",
        "first_name": "Juma",
        "last_name": "Trader",
        "role": Profile.Role.ENTREPRENEUR,
        "phone_number": "+255700000003",
        "organization": "Dar Fresh Produce",
    },
    {
        "username": "buyer_sample",
        "email": "system.buyer@user.com",
        "first_name": "Neema",
        "last_name": "Buyer",
        "role": Profile.Role.BUYER,
        "phone_number": "+255700000004",
        "organization": "Market Buyers Ltd",
    },
    {
        "username": "market_officer_sample",
        "email": "system.market_officer@user.com",
        "first_name": "Grace",
        "last_name": "Officer",
        "role": Profile.Role.MARKET_OFFICER,
        "phone_number": "+255700000005",
        "organization": "Market Office",
        "is_staff": True,
    },
    {
        "username": "researcher_sample",
        "email": "system.researcher@user.com",
        "first_name": "David",
        "last_name": "Researcher",
        "role": Profile.Role.RESEARCHER,
        "phone_number": "+255700000006",
        "organization": "DIT Research Unit",
    },
]


class Command(BaseCommand):
    help = "Seed verified sample system users for all default roles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="StrongPass123",
            help="Password assigned to all seeded sample users. Defaults to StrongPass123.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        User = get_user_model()
        verified_at = timezone.now()
        created_count = 0
        updated_count = 0

        roles = {role.code: role for role in Role.objects.filter(code__in=[user["role"] for user in SAMPLE_USERS])}
        missing_roles = sorted({user["role"] for user in SAMPLE_USERS} - set(roles))
        if missing_roles:
            raise CommandError(
                "Missing role rows: "
                f"{', '.join(missing_roles)}. Run migrations first so system roles are seeded."
            )

        for sample in SAMPLE_USERS:
            defaults = {
                "email": sample["email"],
                "first_name": sample["first_name"],
                "last_name": sample["last_name"],
                "is_active": True,
                "is_staff": sample.get("is_staff", False),
                "is_superuser": sample.get("is_superuser", False),
            }
            user, created = User.objects.update_or_create(
                username=sample["username"],
                defaults=defaults,
            )
            user.set_password(password)
            user.save(update_fields=["password"])

            Profile.objects.update_or_create(
                user=user,
                defaults={
                    "role": roles[sample["role"]],
                    "phone_number": sample["phone_number"],
                    "organization": sample["organization"],
                    "email_verified_at": verified_at,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded verified sample users. Created: {created_count}. Updated: {updated_count}. "
                f"Password: {password}"
            )
        )
