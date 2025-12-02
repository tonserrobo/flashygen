notion_url = "https://www.notion.so/Modern-C-Essentials-295351e37d4681819a44c78272d56687?source=copy_link"

## C++11 Features

### Auto Type Deduction

```cpp
auto x = 42;              // int
auto y = 3.14;            // double
auto str = "hello"s;      // std::string (with 's' literal)
auto vec = std::vector<int>{1, 2, 3};

// Function return type deduction (C++14)
auto add(int a, int b) { return a + b; }
```

### Range-Based For Loops

```cpp
std::vector<int> vec = {1, 2, 3, 4, 5};

// Read-only access
for (const auto& elem : vec) {
    std::cout << elem << " ";
}

// Modify elements
for (auto& elem : vec) {
    elem *= 2;
}
```

### Uniform Initialization

```cpp
int x{5};                     // Value initialization
std::vector<int> vec{1, 2, 3}; // Initializer list
std::string str{"hello"};      // Prevents narrowing conversions

struct Point { int x, y; };
Point p{10, 20};              // Aggregate initialization
```

### Move Semantics (Brief Overview)

```cpp
std::vector<int> v1 = {1, 2, 3};
std::vector<int> v2 = std::move(v1);  // v1 is now in valid but unspecified state
// See "Move Semantics & Perfect Forwarding" for details
```

### Lambda Expressions

```cpp
// Basic lambda
auto add = [](int a, int b) { return a + b; };

// Capture by value
int x = 10;
auto add_x = [x](int a) { return a + x; };

// Capture by reference
auto increment = [&x]() { x++; };

// Capture all by value
auto lambda1 = [=]() { /* use any local variable */ };

// Capture all by reference
auto lambda2 = [&]() { /* modify any local variable */ };

// Generic lambda (C++14)
auto print = [](const auto& val) { std::cout << val; };
```

### nullptr

```cpp
int* ptr = nullptr;  // Much safer than NULL or 0

if (ptr == nullptr) {
    // Handle null pointer
}
```

### Smart Pointers (Brief)

```cpp
#include <memory>

// Unique ownership
std::unique_ptr<int> ptr1 = std::make_unique<int>(42);

// Shared ownership
std::shared_ptr<int> ptr2 = std::make_shared<int>(42);

// See "Smart Pointers & RAII" for comprehensive coverage
```

### Threading Support

```cpp
#include <thread>

void worker() { /* do work */ }

std::thread t(worker);
t.join();  // Wait for thread to finish
```

## C++14 Features

### Generic Lambdas

```cpp
auto generic_add = [](auto a, auto b) { return a + b; };

int i = generic_add(1, 2);           // int + int
double d = generic_add(1.5, 2.5);    // double + double
```

### Return Type Deduction

```cpp
auto multiply(int a, int b) {
    return a * b;  // Compiler deduces return type
}
```

### Binary Literals and Digit Separators

```cpp
int binary = 0b1010'1010;  // 170 in decimal
int large = 1'000'000;     // More readable
```

### std::make_unique

```cpp
auto ptr = std::make_unique<int>(42);
```

## C++17 Features

### Structured Bindings

```cpp
std::pair<int, std::string> getPair() {
    return {1, "hello"};
}

auto [num, str] = getPair();  // Decompose pair

// With maps
std::map<int, std::string> m = {{1, "one"}, {2, "two"}};
for (const auto& [key, value] : m) {
    std::cout << key << ": " << value << "\n";
}
```

### if/switch with Initializer

```cpp
if (auto it = map.find(key); it != map.end()) {
    // Use it here
}

switch (auto val = getValue(); val) {
    case 1: /* handle */; break;
    case 2: /* handle */; break;
}
```

### std::optional

```cpp
#include <optional>

std::optional<int> maybeInt(bool success) {
    if (success) return 42;
    return std::nullopt;
}

if (auto result = maybeInt(true)) {
    std::cout << "Got: " << *result;
} else {
    std::cout << "No value";
}
```

### std::variant

```cpp
#include <variant>

std::variant<int, double, std::string> v = 42;
v = 3.14;
v = "hello";

std::visit([](auto&& arg) {
    std::cout << arg;
}, v);
```

### Filesystem Library

```cpp
#include <filesystem>
namespace fs = std::filesystem;

fs::path p = "/path/to/file.txt";
if (fs::exists(p)) {
    auto size = fs::file_size(p);
}
```

## C++20 Features

### Concepts

```cpp
#include <concepts>

template<typename T>
concept Numeric = std::integral<T> || std::floating_point<T>;

template<Numeric T>
T add(T a, T b) {
    return a + b;
}
```

### Ranges

```cpp
#include <ranges>

std::vector<int> vec = {1, 2, 3, 4, 5};

auto result = vec
    | std::views::filter([](int n) { return n % 2 == 0; })
    | std::views::transform([](int n) { return n * 2; });
```

### Three-Way Comparison (Spaceship Operator)

```cpp
#include <compare>

struct Point {
    int x, y;
    auto operator<=>(const Point&) const = default;
};

Point p1{1, 2}, p2{1, 3};
if (p1 < p2) { /* ... */ }
```

### Designated Initializers

```cpp
struct Config {
    int width = 800;
    int height = 600;
    bool fullscreen = false;
};

Config cfg{
    .width = 1920,
    .height = 1080,
    .fullscreen = true
};
```

### Coroutines (Basic)

```cpp
#include <coroutine>

// Simplified generator example
Generator<int> range(int start, int end) {
    for (int i = start; i < end; ++i) {
        co_yield i;
    }
}
```

## C++23 Features

### std::expected

```cpp
#include <expected>

std::expected<int, std::string> divide(int a, int b) {
    if (b == 0) {
        return std::unexpected("Division by zero");
    }
    return a / b;
}

if (auto result = divide(10, 2)) {
    std::cout << "Result: " << *result;
} else {
    std::cout << "Error: " << result.error();
}
```

### Deducing this

```cpp
struct Logger {
    void log(this Logger const& self, std::string msg) {
        // Explicit object parameter - enables CRTP-like patterns
    }
};
```

### std::mdspan (Multidimensional Array View)

```cpp
#include <mdspan>

std::vector<int> data(12);
std::mdspan<int, std::extents<int, 3, 4>> matrix([data.data](http://data.data)());
matrix[1, 2] = 42;  // Access 2D array
```

## Best Practices

### Prefer Modern Features

- Use `auto` for complex types and iterators
- Prefer smart pointers over raw pointers
- Use range-based for loops when possible
- Embrace structured bindings for clarity
- Use `std::optional` instead of null pointers for optional values

### Performance Considerations

- Move semantics are optimization, not correctness
- Lambdas have zero overhead when not capturing
- `constexpr` enables compile-time computation
- Ranges can be composed without intermediate copies

## Related Topics

- **Type System & Type Deduction** - Deep dive into auto, decltype, and type inference
- **Move Semantics & Perfect Forwarding** - Comprehensive move semantics guide
- **Templates & Metaprogramming** - Template features across standards
- **Smart Pointers & RAII** - Memory management patterns
