from faker import Faker

def generate_data(n=100):
    """Generate synthetic data."""
    fake = Faker()
    data = []
    for i in range(n):
        data.append({
            'id': i,
            'a': fake.random_int(1, 100),
            'b': fake.random_int(1, 100)
        })
    return data