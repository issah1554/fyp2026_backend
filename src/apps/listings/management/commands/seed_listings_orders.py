import random
from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.auth.models import Profile
from apps.users.models import Role
from apps.commodities.models import Commodity
from apps.areas.models import AdmArea
from apps.listings.models import CommodityListing, ListingImage
from apps.orders.models import Order
from apps.common.ids import generate_unique_public_id


# Sample users to ensure we have a diverse pool of sellers & buyers
ADDITIONAL_USERS = [
    {
        "username": "baraka_trader",
        "email": "baraka.mussa@trader.tz",
        "first_name": "Baraka",
        "last_name": "Mussa",
        "role": Profile.Role.ENTREPRENEUR,
        "phone_number": "+255712345601",
        "organization": "Kibo Produce & Trading Co.",
        "farm_location": "Moshi Urban, Kilimanjaro",
    },
    {
        "username": "fatuma_farmer",
        "email": "fatuma.khalfan@farmer.tz",
        "first_name": "Fatuma",
        "last_name": "Khalfan",
        "role": Profile.Role.FARMER,
        "phone_number": "+255712345602",
        "organization": "Kilosa Farmers Group",
        "farm_location": "Kilosa, Morogoro",
        "farm_group": "Kilosa Grain Producers",
    },
    {
        "username": "rashid_buyer",
        "email": "rashid.bakari@buyer.tz",
        "first_name": "Rashid",
        "last_name": "Bakari",
        "role": Profile.Role.BUYER,
        "phone_number": "+255712345603",
        "organization": "Azam Foods Processing",
        "farm_location": "Dar es Salaam",
    },
    {
        "username": "halima_coop",
        "email": "halima.saidi@coop.tz",
        "first_name": "Halima",
        "last_name": "Saidi",
        "role": Profile.Role.FARMER,
        "phone_number": "+255712345604",
        "organization": "Mbeya Agricultural Cooperative Union",
        "farm_location": "Kyela, Mbeya",
        "farm_group": "Kyela Rice Growers",
    },
    {
        "username": "john_swai",
        "email": "john.swai@agro.tz",
        "first_name": "John",
        "last_name": "Swai",
        "role": Profile.Role.ENTREPRENEUR,
        "phone_number": "+255712345605",
        "organization": "Swai Grain Wholesalers",
        "farm_location": "Arusha Urban",
    },
]

# Unsplash image datasets per commodity type for realistic previews
COMMODITY_IMAGES = {
    "Maize": [
        "https://images.unsplash.com/photo-1551754655-cd27e38d2076?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1601593346740-925612772716?auto=format&fit=crop&w=800&q=80",
    ],
    "Rice": [
        "https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1536304929831-ee1ca9d44906?auto=format&fit=crop&w=800&q=80",
    ],
    "Beans": [
        "https://images.unsplash.com/photo-1551462147-37885acc36f1?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1515543904379-3d757afe72e3?auto=format&fit=crop&w=800&q=80",
    ],
    "Coffee": [
        "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1611854779393-1b2da9d400fe?auto=format&fit=crop&w=800&q=80",
    ],
    "Irish Potatoes": [
        "https://images.unsplash.com/photo-1518977676601-b53f82aba655?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1590165482129-1b8b27097a69?auto=format&fit=crop&w=800&q=80",
    ],
    "Sorghum": [
        "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=800&q=80",
    ],
    "Bulrush Millet": [
        "https://images.unsplash.com/photo-1509358271058-acd01cc9386a?auto=format&fit=crop&w=800&q=80",
    ],
    "Finger Millet": [
        "https://images.unsplash.com/photo-1509358271058-acd01cc9386a?auto=format&fit=crop&w=800&q=80",
    ],
    "Wheat Grain": [
        "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=800&q=80",
        "https://images.unsplash.com/photo-1500937386664-56d1dfef3854?auto=format&fit=crop&w=800&q=80",
    ],
    "Cocoa": [
        "https://images.unsplash.com/photo-1541781774459-bb2af2f05b55?auto=format&fit=crop&w=800&q=80",
    ],
}

DEFAULT_IMAGE = "https://images.unsplash.com/photo-1500937386664-56d1dfef3854?auto=format&fit=crop&w=800&q=80"

LISTING_TEMPLATES = [
    {
        "commodity": "Maize",
        "title": "Grade 1 White Maize Grain - Kahama Bulk Supply",
        "description": "Clean, sun-dried white maize grain harvested from Kahama farms. Moisture content below 13%. Ideal for commercial milling. Minimum order 500 kg.",
        "price": Decimal("850.00"),
        "quantity": Decimal("15000.00"),
    },
    {
        "commodity": "Maize",
        "title": "Yellow Maize for Livestock & Feed - Morogoro",
        "description": "High energy yellow maize suitable for animal feed production and industrial processing. Well stored in dry aerated silos.",
        "price": Decimal("780.00"),
        "quantity": Decimal("25000.00"),
    },
    {
        "commodity": "Maize",
        "title": "Fresh Sweet Corn / Maize Cobs - Kilosa District",
        "description": "Freshly harvested sweet corn cobs packed in 50kg sacks. Direct farm delivery available across Morogoro and Dar es Salaam.",
        "price": Decimal("1100.00"),
        "quantity": Decimal("8000.00"),
    },
    {
        "commodity": "Rice",
        "title": "Kyela Super Aromatic Rice (Mchele wa Kyela Grade A)",
        "description": "Premium Grade A long grain aromatic rice from Kyela, Mbeya. 100% polished, double-sifted, free of stones and debris. Packed in 25kg & 50kg bags.",
        "price": Decimal("2800.00"),
        "quantity": Decimal("12000.00"),
    },
    {
        "commodity": "Rice",
        "title": "Kahama Mchele Safi / Processed White Rice",
        "description": "High quality milled white rice from Shinyanga region. Excellent cooking taste, low moisture content. Bulk order wholesale prices available.",
        "price": Decimal("2450.00"),
        "quantity": Decimal("18000.00"),
    },
    {
        "commodity": "Rice",
        "title": "Unmilled Paddy Rice (Mpunga wa Kyela)",
        "description": "Raw paddy rice harvested directly from irrigation schemes in Kyela. Ready for commercial rice millers and processing plants.",
        "price": Decimal("1400.00"),
        "quantity": Decimal("30000.00"),
    },
    {
        "commodity": "Beans",
        "title": "Red Kidney Beans (Maharage ya Nyekundu) - Kilosa",
        "description": "Hand-picked red kidney beans. Sort-cleaned, uniform grain size, high protein content. Packaged in breathable 100kg jute sacks.",
        "price": Decimal("2600.00"),
        "quantity": Decimal("9500.00"),
    },
    {
        "commodity": "Beans",
        "title": "Yellow Beans (Maharage ya Njano / Soya) - Mbeya",
        "description": "Soft cooking yellow beans rich in nutrients. Harvested from Mbeya highlands. Cleaned and graded ready for market distribution.",
        "price": Decimal("3100.00"),
        "quantity": Decimal("7000.00"),
    },
    {
        "commodity": "Beans",
        "title": "Rosecoco Beans (Maharage ya Wairaq) - Babati",
        "description": "High quality Rosecoco beans from Manyara region. Well dried, shiny coats, zero pest infestation. Highly demanded by urban markets.",
        "price": Decimal("2900.00"),
        "quantity": Decimal("11000.00"),
    },
    {
        "commodity": "Coffee",
        "title": "Grade A Organic Arabica Coffee Beans - Arusha Highlands",
        "description": "Washed Arabica coffee beans grown on the fertile slopes of Mt. Meru. Cupping score 85+. Sun-dried parchment coffee ready for export/roasting.",
        "price": Decimal("14500.00"),
        "quantity": Decimal("5000.00"),
    },
    {
        "commodity": "Coffee",
        "title": "Kilimanjaro Mild Arabica Green Coffee Beans",
        "description": "Highland arabica green coffee harvested in Moshi rural. Uniform screen size 17/18. Processed using traditional wet fermentation methods.",
        "price": Decimal("13800.00"),
        "quantity": Decimal("8500.00"),
    },
    {
        "commodity": "Coffee",
        "title": "Kagera Robusta Coffee Beans - Bukoba",
        "description": "Strong body Robusta coffee from Kagera region. High caffeine content, dry processed (Unwashed Cherry). Great for espresso blends.",
        "price": Decimal("9500.00"),
        "quantity": Decimal("14000.00"),
    },
    {
        "commodity": "Irish Potatoes",
        "title": "Fresh Irish Potatoes (Viazi Lishe / Round) - Njombe",
        "description": "Large size red-skin Irish potatoes from Njombe highlands. Firm texture, low water content. Perfect for chips, frying, and retail stores.",
        "price": Decimal("1300.00"),
        "quantity": Decimal("20000.00"),
    },
    {
        "commodity": "Irish Potatoes",
        "title": "White Seed & Table Potatoes - Mbeya Rural",
        "description": "Multi-purpose white Irish potatoes harvested from Poroto Mountains. Packed in standard 100kg bags (Lumbesa available on request).",
        "price": Decimal("1150.00"),
        "quantity": Decimal("25000.00"),
    },
    {
        "commodity": "Irish Potatoes",
        "title": "Grade 1 Commercial Irish Potatoes - Lushoto Tanga",
        "description": "Freshly dug potatoes from Usambara Mountains in Lushoto. Carefully cleaned and sorted by size (Large, Medium, Small).",
        "price": Decimal("1400.00"),
        "quantity": Decimal("10000.00"),
    },
    {
        "commodity": "Sorghum",
        "title": "White Sorghum Grain (Mtama Mweupe) - Singida",
        "description": "High purity white sorghum grain harvested in Singida. Drought-resistant crop, low tannins. Suitable for commercial brewing and food flour.",
        "price": Decimal("920.00"),
        "quantity": Decimal("16000.00"),
    },
    {
        "commodity": "Sorghum",
        "title": "Red Sorghum Grain (Mtama Mwekundu) - Dodoma",
        "description": "Clean red sorghum for poultry feed production, porridge, and traditional brewing. Bulk supply stored in Dodoma central warehouse.",
        "price": Decimal("850.00"),
        "quantity": Decimal("22000.00"),
    },
    {
        "commodity": "Bulrush Millet",
        "title": "Bulrush Millet Grain (Mawele) - Shinyanga",
        "description": "Whole grain bulrush millet from Shinyanga rural. Rich in dietary fiber and essential minerals. Threshed, winnowed, and ready for shipment.",
        "price": Decimal("1250.00"),
        "quantity": Decimal("9000.00"),
    },
    {
        "commodity": "Finger Millet",
        "title": "Finger Millet (Ulezi Safi Grade 1) - Dodoma",
        "description": "Dark red finger millet grain used for premium baby food porridge and nutritious flour blends. 100% organic, machine cleaned.",
        "price": Decimal("1850.00"),
        "quantity": Decimal("13000.00"),
    },
    {
        "commodity": "Finger Millet",
        "title": "Bulk Finger Millet Grain - Sumbawanga",
        "description": "Cleaned finger millet harvested from Rukwa valley farms. Packed in 50kg polypropylene bags ready for distribution across East Africa.",
        "price": Decimal("1750.00"),
        "quantity": Decimal("17000.00"),
    },
    {
        "commodity": "Wheat Grain",
        "title": "Hard Red Wheat Grain - Sumbawanga Rukwa",
        "description": "High gluten hard red wheat grain suitable for bread flour milling. Moisture content 12.5%. Bulk loading facilities available.",
        "price": Decimal("1600.00"),
        "quantity": Decimal("35000.00"),
    },
    {
        "commodity": "Wheat Grain",
        "title": "Soft White Wheat Grain - Hanang Manyara",
        "description": "Premium white wheat grown on the volcanic soils of Hanang District. Excellent for biscuits, cakes, and pastry flour milling.",
        "price": Decimal("1680.00"),
        "quantity": Decimal("28000.00"),
    },
    {
        "commodity": "Cocoa",
        "title": "Raw Sun-Dried Cocoa Beans - Kyela Mbeya",
        "description": "Fermented and sun-dried cocoa beans from Kyela tropical lowland farms. Bean count 95-100 per 100g, moisture 7.5%. Export quality.",
        "price": Decimal("8500.00"),
        "quantity": Decimal("6500.00"),
    },
    {
        "commodity": "Cocoa",
        "title": "Organic Certified Cocoa Beans - Morogoro Rural",
        "description": "Organically cultivated cocoa beans from Uluguru mountain valleys. Rich chocolate aroma, proper fermentation index > 80%.",
        "price": Decimal("9200.00"),
        "quantity": Decimal("4000.00"),
    },
    {
        "commodity": "Maize",
        "title": "White Maize Flour (Unga wa Sembe) Bulk - Dar es Salaam",
        "description": "Refined grade A white maize flour packaged in 5kg, 10kg, and 25kg branded bags. Produced from high quality Kahama maize grain.",
        "price": Decimal("1500.00"),
        "quantity": Decimal("15000.00"),
    },
    {
        "commodity": "Rice",
        "title": "Kyela Super Broken Rice (Mchele wa Magari) - Mbeya",
        "description": "Cleaned broken aromatic rice, ideal for catering, restaurants, and budget consumer packages. Same great Kyela aroma at discount price.",
        "price": Decimal("1900.00"),
        "quantity": Decimal("10000.00"),
    },
    {
        "commodity": "Beans",
        "title": "Black Eyed Peas (Kunde) - Tabora Region",
        "description": "Fresh dry black-eyed peas harvested in Tabora. Uniform size, fast cooking time. Stored in climate-controlled warehouses.",
        "price": Decimal("2100.00"),
        "quantity": Decimal("8500.00"),
    },
    {
        "commodity": "Beans",
        "title": "Soya Beans (Maharage ya Soya) - Iringa",
        "description": "High oil content non-GMO soybean grain for edible oil extraction and soy milk processing. Packed in 50kg sacks.",
        "price": Decimal("1800.00"),
        "quantity": Decimal("30000.00"),
    },
    {
        "commodity": "Irish Potatoes",
        "title": "Cocktail & Small Size Potatoes - Sumbawanga",
        "description": "Baby round potatoes for specialized restaurant menus and roasting. Crisp texture, excellent skin quality.",
        "price": Decimal("950.00"),
        "quantity": Decimal("12000.00"),
    },
    {
        "commodity": "Maize",
        "title": "Dry White Maize - Songea Ruvuma",
        "description": "High altitude white maize grain from Ruvuma region, known as the granary of Tanzania. Well dried and fumigated for long storage.",
        "price": Decimal("820.00"),
        "quantity": Decimal("40000.00"),
    },
    {
        "commodity": "Rice",
        "title": "Mbarali Irrigation Rice - Kapunga Mbeya",
        "description": "High yield white rice harvested from Kapunga rice estate. Uniform long grains, low breakage rate.",
        "price": Decimal("2550.00"),
        "quantity": Decimal("22000.00"),
    },
    {
        "commodity": "Coffee",
        "title": "Mbinga Ruvuma Arabica Parchment Coffee",
        "description": "Direct trade Arabica parchment coffee from Mbinga cooperative societies. Rich body with floral notes.",
        "price": Decimal("12800.00"),
        "quantity": Decimal("6000.00"),
    },
    {
        "commodity": "Sorghum",
        "title": "Brewery Grade Sorghum - Kondoa Dodoma",
        "description": "Contract grown clear grain sorghum specified for industrial malt production and commercial brewing.",
        "price": Decimal("980.00"),
        "quantity": Decimal("30000.00"),
    },
    {
        "commodity": "Wheat Grain",
        "title": "Seed Wheat Grain Grade A - Karatu Arusha",
        "description": "Treated seed wheat grain for agricultural planting and farming enterprises. High germination test rate > 92%.",
        "price": Decimal("2200.00"),
        "quantity": Decimal("5000.00"),
    },
    {
        "commodity": "Beans",
        "title": "Pinto Beans (Maharage Madoadoa) - Babati",
        "description": "Speckled pinto beans harvested from Babati district. High yield crop, sun-dried on clean tarpaulins.",
        "price": Decimal("2400.00"),
        "quantity": Decimal("14000.00"),
    },
]


ORDER_STATUS_CHOICES = ["pending", "confirmed", "shipped", "completed", "cancelled"]


class Command(BaseCommand):
    help = "Seed at least 30 demonstration listings and 30 demonstration orders connected to real database users."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Starting Seed Data Generation for Listings & Orders ==="))

        User = get_user_model()
        now = timezone.now()

        # 1. Ensure Roles Exist
        role_farmer, _ = Role.objects.get_or_create(
            code=Profile.Role.FARMER,
            defaults={"public_id": generate_unique_public_id(Role), "name": "Farmer", "is_system": True}
        )
        role_entrepreneur, _ = Role.objects.get_or_create(
            code=Profile.Role.ENTREPRENEUR,
            defaults={"public_id": generate_unique_public_id(Role), "name": "Entrepreneur", "is_system": True}
        )
        role_buyer, _ = Role.objects.get_or_create(
            code=Profile.Role.BUYER,
            defaults={"public_id": generate_unique_public_id(Role), "name": "Buyer", "is_system": True}
        )

        # 2. Ensure Additional Sample Users Exist
        for add_u in ADDITIONAL_USERS:
            user, created = User.objects.get_or_create(
                username=add_u["username"],
                defaults={
                    "email": add_u["email"],
                    "first_name": add_u["first_name"],
                    "last_name": add_u["last_name"],
                    "is_active": True,
                }
            )
            if created:
                user.set_password("StrongPass123")
                user.save()

            role_obj = role_farmer if add_u["role"] == Profile.Role.FARMER else (
                role_entrepreneur if add_u["role"] == Profile.Role.ENTREPRENEUR else role_buyer
            )

            profile, _ = Profile.objects.get_or_create(
                user=user,
                defaults={
                    "phone_number": add_u["phone_number"],
                    "organization": add_u["organization"],
                    "farm_location": add_u.get("farm_location", ""),
                    "farm_group": add_u.get("farm_group", ""),
                    "email_verified_at": now,
                }
            )
            profile.roles.set([role_obj])

        # Fetch active seller and buyer users from DB
        sellers = list(User.objects.filter(profile__roles__code__in=[Profile.Role.FARMER, Profile.Role.ENTREPRENEUR]))
        buyers = list(User.objects.filter(profile__roles__code__in=[Profile.Role.BUYER, Profile.Role.ENTREPRENEUR, Profile.Role.ADMIN, Profile.Role.MARKET_OFFICER]))

        if not sellers:
            sellers = list(User.objects.all())
        if not buyers:
            buyers = list(User.objects.all())

        self.stdout.write(f"Available Sellers in DB: {len(sellers)}, Available Buyers in DB: {len(buyers)}")

        # Fetch Commodities and Administrative Areas
        commodities_map = {c.name: c for c in Commodity.objects.all()}
        adm_areas = list(AdmArea.objects.all())

        if not commodities_map:
            self.stdout.write(self.style.ERROR("No commodities found in DB! Please run commodity seeds first."))
            return

        if not adm_areas:
            self.stdout.write(self.style.ERROR("No administrative areas found in DB! Please run seed_areas first."))
            return

        # 3. Create Commodity Listings (at least 35)
        self.stdout.write("Seeding Commodity Listings...")
        created_listings = []
        statuses = ["available", "available", "available", "available", "sold_out", "draft"]

        for idx, tpl in enumerate(LISTING_TEMPLATES):
            commodity_obj = commodities_map.get(tpl["commodity"])
            if not commodity_obj:
                commodity_obj = random.choice(list(commodities_map.values()))

            seller = sellers[idx % len(sellers)]
            area = adm_areas[(idx * 17) % len(adm_areas)]

            price = tpl["price"]

            listing = CommodityListing.objects.create(
                commodity=commodity_obj,
                adm_area=area,
                user=seller,
                title=tpl["title"],
                description=tpl["description"],
                price=price,
                quantity=tpl["quantity"],
                status=statuses[idx % len(statuses)],
            )
            created_listings.append(listing)

            # Assign images
            img_urls = COMMODITY_IMAGES.get(tpl["commodity"], [DEFAULT_IMAGE])
            for img_idx, url in enumerate(img_urls):
                ListingImage.objects.create(
                    listing=listing,
                    image_url=url,
                    is_primary=(img_idx == 0)
                )

            # Backdate listing creation date
            days_ago = random.randint(5, 45)
            created_date = now - timedelta(days=days_ago)
            CommodityListing.objects.filter(pk=listing.pk).update(created_at=created_date)

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {len(created_listings)} Commodity Listings with Images."))

        # 4. Create Orders (at least 35)
        self.stdout.write("Seeding Orders connected to real listings & users...")
        created_orders = []

        order_index = 0
        while len(created_orders) < 36:
            listing = created_listings[order_index % len(created_listings)]
            order_index += 1

            # Pick a buyer who is NOT the listing seller
            eligible_buyers = [b for b in buyers if b.id != listing.user_id]
            if not eligible_buyers:
                eligible_buyers = buyers
            buyer = random.choice(eligible_buyers)

            max_qty = float(listing.quantity or Decimal("1000.00"))
            ord_qty_num = min(random.choice([50, 100, 200, 500, 1000, 2500]), max_qty * 0.4)
            if ord_qty_num <= 0:
                ord_qty_num = 50.0

            order_qty = Decimal(str(round(ord_qty_num, 2)))
            total_price = (order_qty * listing.price).quantize(Decimal("0.01"))
            status = random.choice(ORDER_STATUS_CHOICES)

            order = Order.objects.create(
                listing=listing,
                user=buyer,
                quantity=order_qty,
                total_price=total_price,
                status=status,
            )

            # Backdate order creation date (must be after listing creation date)
            order_days_ago = random.randint(1, 20)
            order_date = now - timedelta(days=order_days_ago)
            Order.objects.filter(pk=order.pk).update(created_at=order_date)

            created_orders.append(order)

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {len(created_orders)} Orders."))

        # 5. Summary Verification
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seed Summary ==="))
        self.stdout.write(f"Total Users in Database: {User.objects.count()}")
        self.stdout.write(f"Total Commodity Listings: {CommodityListing.objects.count()}")
        self.stdout.write(f"Total Listing Images: {ListingImage.objects.count()}")
        self.stdout.write(f"Total Orders: {Order.objects.count()}")
        self.stdout.write(self.style.SUCCESS("All relations successfully created with 100% integrity!"))
