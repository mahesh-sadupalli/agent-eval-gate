"""Local BFCL exec_simple functions, copied from Gorilla at commit
4d05b53fce8a2055957311817f6c7f9143acdc11,
berkeley-function-call-leaderboard/bfcl/eval_checker/executable_eval/executable_python_function.py

Copyright the Gorilla / BFCL authors, Apache License 2.0
(https://www.apache.org/licenses/LICENSE-2.0).

Modified for this project (PROTOCOL.md section 2): kept only the 30 local
functions the 60-case pilot uses, in upstream order, with bodies unchanged;
removed the import-time API-key check, the `requests`/`os`/`time` imports, and
every remote-service function. tests/test_verifier.py checks each body
against the pinned upstream file.
"""
import math

def calculate_triangle_area(base, height):
    """
    Calculates the area of a triangle.
    Args:
        base (integer): The base of the triangle.
        height (integer): The height of the triangle.
    """
    return base * height / 2

def get_distance(pointA, pointB):
    """
    Calculates the distance between two 2D points.
    Args:
        pointA (tuple): The first point.
        pointB (tuple): The second point.
    """
    return ((pointA[0] - pointB[0]) ** 2 + (pointA[1] - pointB[1]) ** 2) ** 0.5

def math_factorial(n):
    """
    Calculates the factorial of a number.
    Args:
        n (integer): The number to calculate the factorial of.
    """
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result

def quadratic_roots(a, b, c):
    """
    Calculates the roots of a quadratic equation.
    Args:
        a (integer): The first coefficient.
        b (integer): The second coefficient.
        c (integer): The third coefficient.
    Returns:
        A list of roots, where each root is either a float or a dictionary
        with 'real' and 'imaginary' parts for complex roots.
    """
    discriminant = b**2 - 4 * a * c
    if discriminant >= 0:
        root1 = (-b + discriminant**0.5) / (2 * a)
        root2 = (-b - discriminant**0.5) / (2 * a)
        roots = [root1, root2]
    else:
        real_part = -b / (2 * a)
        imaginary_part = (abs(discriminant) ** 0.5) / (2 * a)
        roots = [
            {"real": real_part, "imaginary": imaginary_part},
            {"real": real_part, "imaginary": -imaginary_part},
        ]

    return roots

def geometry_area_circle(radius):
    """
    Calculates the area of a circle.
    Args:
        radius (integer): The radius of the circle.
    """
    return math.pi * radius**2

def get_prime_factors(number):
    """
    Calculates the prime factors of a number.
    Args:
        number (integer): The number to calculate the prime factors of.
    """
    factors = []
    divisor = 2
    while number > 1:
        while number % divisor == 0:
            factors.append(divisor)
            number /= divisor
        divisor += 1
    return factors

def math_gcd(a, b):
    """
    Calculates the greatest common divisor of two numbers.
    Args:
        a (integer): The first number. This should be the larger number.
        b (integer): The second number.
    """
    if b == 0:
        return a
    else:
        return math_gcd(b, a % b)

def math_lcm(a, b):
    """
    Calculates the least common multiple of two numbers.
    Args:
        a (integer): The first number. This should be the larger number.
        b (integer): The second number.
    """
    return a * b / math_gcd(a, b)

def calculate_final_velocity(initial_velocity, acceleration, time):
    """
    Calculates the final velocity of an object.
    Args:
        initial_velocity (integer): The initial velocity of the object.
        acceleration (integer): The acceleration of the object.
        time (integer): The time the object has been moving.
    """
    return initial_velocity + acceleration * time

def calculate_displacement(initial_velocity, acceleration, time):
    """
    Calculates the displacement of an object.
    Args:
        initial_velocity (integer): The initial velocity of the object.
        acceleration (integer): The acceleration of the object.
        time (integer): The time the object has been moving.
    """
    return initial_velocity * time + 0.5 * acceleration * time**2

def calculate_electrostatic_potential_energy(charge, voltage):
    """
    Calculates the electrostatic potential energy.
    Args:
        charge (integer): The charge of the object.
        voltage (integer): The voltage of the object.
    """
    return charge * voltage

def calculate_density(mass, volume):
    """
    Calculates the density of an object.
    Args:
        mass (integer): The mass of the object.
        volume (integer): The volume of the object.
    """
    return mass / volume

def mat_mul(matA, matB):
    """
    Multiplies two matrices.
    Args:
        matA (list): The first matrix.
        matB (list): The second matrix.
    """
    result = [[0 for i in range(len(matB[0]))] for j in range(len(matA))]
    for i in range(len(matA)):
        for j in range(len(matB[0])):
            for k in range(len(matB)):
                result[i][j] += matA[i][k] * matB[k][j]
    return result

def calculate_mean(numbers):
    """
    Calculates the mean of a list of numbers.
    Args:
        numbers (list): The list of numbers.
    """
    return sum(numbers) / len(numbers)

def calculate_standard_deviation(numbers):
    """
    Calculates the standard deviation of a list of numbers.
    Args:
        numbers (list): The list of numbers.
    """
    mean = calculate_mean(numbers)
    variance = sum((number - mean) ** 2 for number in numbers) / len(numbers)
    return variance**0.5

def calc_binomial_probability(n, k, p):
    """
    Calculates the probability of getting k successes in n trials.
    Args:
        n (integer): The number of trials.
        k (integer): The number of successes.
        p (integer): The probability of success.
    """
    return (
        math_factorial(n)
        / (math_factorial(k) * math_factorial(n - k))
        * (p**k * (1 - p) ** (n - k))
    )

def calculate_permutations(n, k):
    """
    Calculates the number of permutations of k elements from a set of n elements.
    Args:
        n (integer): The number of elements in the set.
        k (integer): The number of elements to choose.
    """
    return math_factorial(n) / math_factorial(n - k)

def get_fibonacci_sequence(n):
    """
    Calculates the n numbers of the Fibonacci.
    Args:
        n (integer): The number of Fibonacci numbers to calculate.
    """
    sequence = [0, 1]
    for i in range(2, n):
        sequence.append(sequence[i - 1] + sequence[i - 2])
    return sequence

def calculate_cosine_similarity(vectorA, vectorB):
    """
    Calculates the cosine similarity of two vectors.
    Args:
        vectorA (list): The first vector.
        vectorB (list): The second vector.
    """
    dot_product = sum(vectorA[i] * vectorB[i] for i in range(len(vectorA)))
    magnitudeA = (sum(vectorA[i] ** 2 for i in range(len(vectorA)))) ** 0.5
    magnitudeB = (sum(vectorB[i] ** 2 for i in range(len(vectorB)))) ** 0.5
    return dot_product / (magnitudeA * magnitudeB)

def mortgage_calculator(loan_amount, interest_rate, loan_period):
    """
    Calculates the monthly mortgage payment.
    Args:
        loan_amount (integer): The amount of the loan.
        interest_rate (integer): The interest rate of the loan.
        loan_period (integer): The period of the loan.
    """
    monthly_interest_rate = interest_rate / 12
    number_of_payments = loan_period * 12
    monthly_payment = (
        loan_amount
        * monthly_interest_rate
        * (1 + monthly_interest_rate) ** number_of_payments
        / ((1 + monthly_interest_rate) ** number_of_payments - 1)
    )
    return monthly_payment

def calculate_future_value(present_value, interest_rate, periods):
    """
    Calculates the future value of an investment.
    Args:
        present_value (integer): The present value of the investment.
        interest_rate (integer): The interest rate of the investment.
        periods (integer): The number of periods.
    """
    return present_value * (1 + interest_rate) ** periods

def sort_array(array, reverse=False):
    """
    Sorts an array of numbers.
    Args:
        array (list): The array of numbers.
        reverse (optional bool): Whether to sort the array in reverse order, i.e., descending order.
    """
    return sorted(array, reverse=reverse)

def linear_regression(x, y, point):
    """
    Finds the linear regression of a set of points.
    Args:
        x (list): The x coordinates of the points.
        y (list): The y coordinates of the points.
        point (int): The point to calculate the linear regression at.
    """
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_x_squared = sum(x_i**2 for x_i in x)
    sum_xy = sum(x[i] * y[i] for i in range(n))
    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x_squared - sum_x**2)
    intercept = (sum_y - slope * sum_x) / n
    return slope * point + intercept

def add_binary_numbers(a, b):
    """
    Adds two binary numbers.
    Args:
        a (str): The first binary number.
        b (str): The second binary number.
    """
    return bin(int(a, 2) + int(b, 2))[2:]

def maxPoints(points) -> int:
    """
    Finds the maximum number of points on a line.
    Args:
        points (list): The list of points. points are 2 element lists.
    """
    counter = 1
    if len(points) < 2:
        return 1
    for i in range(len(points)):
        lst = {}
        for j in range(i + 1, len(points)):
            y = points[j][1] - points[i][1]
            x = points[j][0] - points[i][0]
            if x != 0:
                lst[y / x] = 1 + lst.get(y / x, 0)
            else:
                lst["inf"] = 1 + lst.get("inf", 0)
        for key, value in lst.items():
            counter = max(counter, value)
    return counter + 1

def calculate_investment_value(
    initial_investment,
    annual_contribution,
    years,
    annual_return,
    inflation_rate,
    adjust_for_inflation=True,
):
    """
    Calculates the value of an investment over time.
    Args:
        initial_investment (integer): The initial investment amount.
        annual_contribution (integer): The annual contribution amount.
        years (integer): The number of years to calculate the investment value for.
        annual_return (float): The annual return rate, ranging from 0 to 1.
        inflation_rate (list): The inflation rate for each year in percentage, ranging from 0 to 1.
        adjust_for_inflation (optional bool): Whether to adjust the investment value for inflation.
    """
    current_value = initial_investment
    real_value = initial_investment  # Adjusted for inflation

    for year in range(1, years + 1):
        # Apply annual return
        current_value = current_value * (1 + annual_return) + annual_contribution

        # Adjust for inflation if requested
        if adjust_for_inflation:
            inflation_adjustment = (
                1 - inflation_rate[year - 1]
                if year <= len(inflation_rate)
                else 1 - inflation_rate[-1]
            )
            real_value = (
                real_value * (1 + annual_return - inflation_rate[year - 1])
                + annual_contribution * inflation_adjustment
            )
        else:
            real_value = current_value

    final_value = real_value if adjust_for_inflation else current_value
    return final_value

def calculate_nutritional_needs(weight, height, age, gender, activity_level, goal):
    """
    Calculates the nutritional needs of a person based on their weight, height
    Args:
        weight (integer): The weight of the person.
        height (integer): The height of the person.
        age (integer): The age of the person
        gender (str): The gender of the person. Possible options [male,female,other]
        activity_level (integer): The activity level of the person. Possible options [1,2,3,4,5]
        goal (str): The goal of the person. Possible options [lose,gain,maintain]
    """
    if gender == "male":
        bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
    else:
        bmr = 447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age)

    # Total Daily Energy Expenditure (TDEE) Calculation
    activity_multipliers = [1.2, 1.375, 1.55, 1.725, 1.9]
    tdee = bmr * activity_multipliers[activity_level - 1]

    # Adjust TDEE based on goal
    if goal == "lose":
        tdee -= 500  # Creating a deficit to lose weight
    elif goal == "gain":
        tdee += 500  # Creating a surplus to gain weight

    # Macronutrient Distribution
    proteins = (tdee * 0.30) / 4  # 30% of calories from protein, 4 calories per gram
    fats = (tdee * 0.25) / 9  # 25% of calories from fat, 9 calories per gram
    carbohydrates = (tdee * 0.45) / 4  # 45% of calories from carbs, 4 calories per gram

    return {
        "calories": tdee,
        "proteins_g": proteins,
        "fats_g": fats,
        "carbohydrates_g": carbohydrates,
    }

def book_room(
    room_type, price, check_in_date, check_out_date, customer_id, discount_code=None
):
    """
    Books a room for a customer.
    Args:
        room_type (dict): The room type to book.
        check_in_date (str): The check-in date.
        check_out_date (str): The check-out date.
        customer_id (str): The customer ID.
        discount_code (str): The discount code (if any).
    """
    # Assume the first available room is booked (for simplicity)
    booked_room = room_type

    # Calculate price and apply discount if applicable
    if discount_code and discount_code == "DISCOUNT10":
        price *= 0.9  # Apply 10% discount

    booking_details = {
        "customer_id": customer_id,
        "room_number": room_type,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "total_price": price,
    }

    return booking_details

def order_food(item, quantity, price):
    """
    Orders food for a customer.
    Args:
        item (list): The item to order.
        quantity (list): The quantity of the item.
        price (list): The price of the item.
    """
    # Calculate total price
    total_price = sum([quantity[i] * price[i] for i in range(len(item))])
    return total_price

def polygon_area(vertices):
    """
    Calculate the area of a polygon given its vertices using the shoelace formula.
    Args:
        vertices (list): The vertices of the polygon. Vertices are 2 element lists.
    """
    n = len(vertices)
    if n < 3:
        raise ValueError("A polygon must have at least 3 vertices.")

    # Append the first vertex to the end to complete the loop
    vertices.append(vertices[0])

    # Apply the shoelace formula
    area = 0
    for i in range(n):
        area += (vertices[i][0] * vertices[i + 1][1]) - (
            vertices[i + 1][0] * vertices[i][1]
        )

    area = abs(area) / 2.0
    return area


FUNCTIONS = {
    'calculate_triangle_area': calculate_triangle_area,
    'get_distance': get_distance,
    'math_factorial': math_factorial,
    'quadratic_roots': quadratic_roots,
    'geometry_area_circle': geometry_area_circle,
    'get_prime_factors': get_prime_factors,
    'math_gcd': math_gcd,
    'math_lcm': math_lcm,
    'calculate_final_velocity': calculate_final_velocity,
    'calculate_displacement': calculate_displacement,
    'calculate_electrostatic_potential_energy': calculate_electrostatic_potential_energy,
    'calculate_density': calculate_density,
    'mat_mul': mat_mul,
    'calculate_mean': calculate_mean,
    'calculate_standard_deviation': calculate_standard_deviation,
    'calc_binomial_probability': calc_binomial_probability,
    'calculate_permutations': calculate_permutations,
    'get_fibonacci_sequence': get_fibonacci_sequence,
    'calculate_cosine_similarity': calculate_cosine_similarity,
    'mortgage_calculator': mortgage_calculator,
    'calculate_future_value': calculate_future_value,
    'sort_array': sort_array,
    'linear_regression': linear_regression,
    'add_binary_numbers': add_binary_numbers,
    'maxPoints': maxPoints,
    'calculate_investment_value': calculate_investment_value,
    'calculate_nutritional_needs': calculate_nutritional_needs,
    'book_room': book_room,
    'order_food': order_food,
    'polygon_area': polygon_area,
}
