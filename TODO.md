# TODO List

- [ ] AI machine learning model training
- [ ] Data scraping and preprocessing
- [ ] Implementing new features in the application
- [ ] System logging and monitoring (i.e. user activity, errors, performance metrics)
- [ ] Email verification for mobile app users
    [the simmplest way for email verification is to send verification code to the user's email and ask them to enter it in the app to verify their email address because it is compatible with both web and mobile applications]

to simplfiy the logic modify the backend to return all anestros in the same location so that breadcrum logic is simplified so that allthe bread crum shows up correctly even without loading entire locations

e.g
  "data": [
    {
      "area_id": "TrB3xCH3Cp",
      "name": "Arusha",
      "ancestrors": {"region":"AGivenRegion", "distarict":"districtgiven"},
      "level": "ward",
      "created_at": "2026-07-21T04:40:53.352468Z"
    },...