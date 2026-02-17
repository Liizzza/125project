# 125Project Backend Test

This repo contains the backend for the sleep recommender app. To test the backend locally, you can run `tests/test_backend.py` with a Firebase test user.  

### Test User

- Email: test@te.com
- Password: 1231231231
- UID: rieBdTS8KVT2yE4UhBBGIgXoa9f1

### Why Run This Way

- The backend scripts (extract_sleep.py, build_sleep_profile.py, make_sleep_plan.py) are per-user.
- The user_folder is determined from the Firebase UID to ensure each user’s data is isolated.
- `test_backend.py` simulates an iOS client: it logs in the Firebase test user, gets an ID token, and calls the backend exactly as the frontend would.
- This allows full end-to-end testing without needing the iOS app.

### How to Run

1. Activate your Python environment:

    source cs125/bin/activate

2. Start the Flask backend:

    python -m src.backend

3. Make sure the test user folder exists and contains the Apple Health XML:

    mkdir -p users/rieBdTS8KVT2yE4UhBBGIgXoa9f1
    cp ~/Downloads/export.xml users/rieBdTS8KVT2yE4UhBBGIgXoa9f1/

4. Run the test script:

    python -m tests.test_backend

- This will generate the sleep plan and all intermediate files in the test user’s folder.

### Next Steps

- Add the iOS frontend so users can upload their Apple Health XML directly to the correct folder.
- Move per-user data to Firebase Storage for scalable, secure storage instead of keeping it locally.
- Update the backend to read/write from Firebase Storage once integrated.
