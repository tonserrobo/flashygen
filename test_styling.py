"""Test script to verify the improved flashcard styling."""

from flashygen.flashcard_generator import Flashcard
from flashygen.anki_exporter import AnkiExporter

# Create test flashcards with code examples
test_flashcards = [
    Flashcard(
        front="How do you compare and contrast list comprehensions and generator expressions in Python?",
        back="""**List Comprehensions:**

```python
# List comprehension
squares = [x**2 for x in range(5)]
print(squares)  # [0, 1, 4, 9, 16]
```

*List comprehensions create the entire list in memory at once.*

**Generator Expressions:**

```python
# Generator expression
squaresgen = (x**2 for x in range(5))
print(list(squaresgen))  # [0, 1, 4, 9, 16]
```

Generator expressions are *lazy* and generate values on-the-fly.""",
        tags=["python", "comparison"]
    ),
    Flashcard(
        front="What is the difference between `const`, `let`, and `var` in JavaScript?",
        back="""**`const`** - Block-scoped, cannot be reassigned:

```javascript
const PI = 3.14159;
// PI = 3.14; // Error!
```

**`let`** - Block-scoped, can be reassigned:

```javascript
let count = 0;
count = 1; // OK
```

**`var`** - Function-scoped (avoid using):

```javascript
var oldStyle = "legacy";
// Has hoisting issues
```""",
        tags=["javascript", "variables"]
    ),
    Flashcard(
        front="How do you declare and use a struct in Go?",
        back="""**Declaring a struct:**

```go
type Person struct {
    Name string
    Age  int
}
```

**Creating and using:**

```go
func main() {
    // Create instance
    p := Person{
        Name: "Alice",
        Age:  30,
    }

    // Access fields
    fmt.Println(p.Name) // "Alice"
}
```""",
        tags=["go", "structs"]
    ),
]

# Create exporter and generate deck
exporter = AnkiExporter()
output_file = exporter.create_deck(
    flashcards=test_flashcards,
    deck_name="Styling Test Deck",
    output_path="test_styling_deck.apkg"
)

print(f"\n✅ Test deck created: {output_file}")
print("\nImport this deck into Anki to see the improved styling!")
print("\nKey improvements:")
print("  • Modern card design with gradient background")
print("  • Enhanced code block styling with language badges")
print("  • Multi-language syntax highlighting (Python, JavaScript, Go, etc.)")
print("  • Better typography and spacing")
print("  • Box shadows for depth")
print("  • Mobile-responsive design")
