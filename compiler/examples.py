# compiler/examples.py
"""
Example contracts demonstrating jumps, loops, and functions
"""

from compiler.assembler import assemble


def counter_contract() -> list:
    """Simple counter with increment function"""
    source = """
    ; Counter contract
    
    START:
        PUSH 0
        STORE counter
        CALL increment
        CALL increment
        CALL increment
        LOAD counter
        STOP
    
    increment:
        LOAD counter
        PUSH 1
        ADD
        STORE counter
        RETURN
    """
    return assemble(source)


def loop_contract() -> list:
    """Loop that increments counter 10 times"""
    source = """
    ; Loop contract
    
    START:
        PUSH 0
        STORE counter
        PUSH 0
        STORE i
    
    loop:
        LOAD i
        PUSH 10
        LT
        JUMPI end
        
        CALL increment
        LOAD i
        PUSH 1
        ADD
        STORE i
        JUMP loop
    
    increment:
        LOAD counter
        PUSH 1
        ADD
        STORE counter
        RETURN
    
    end:
        STOP
    """
    return assemble(source)


def conditional_contract() -> list:
    """Conditional: returns 1 if value > 10 else 0"""
    source = """
    ; Conditional contract
    
    START:
        LOAD value
        PUSH 10
        GT
        JUMPI greater
        
        PUSH 0
        STORE result
        JUMP end
    
    greater:
        PUSH 1
        STORE result
    
    end:
        LOAD result
        STOP
    """
    return assemble(source)


def fibonacci_contract() -> list:
    """Calculate fibonacci numbers"""
    source = """
    ; Fibonacci calculator
    
    START:
        PUSH 0
        STORE a
        PUSH 1
        STORE b
        PUSH 0
        STORE i
        PUSH 10
        STORE n
    
    fib_loop:
        LOAD i
        LOAD n
        LT
        JUMPI done
        
        CALL next_fib
        LOAD i
        PUSH 1
        ADD
        STORE i
        JUMP fib_loop
    
    next_fib:
        LOAD b
        STORE temp
        LOAD a
        LOAD b
        ADD
        STORE b
        LOAD temp
        STORE a
        RETURN
    
    done:
        LOAD b
        STOP
    """
    return assemble(source)


def simple_if() -> list:
    """Simple if-else example"""
    source = """
    ; Simple if-else
    
    START:
        PUSH x
        LOAD
        PUSH 5
        GT
        JUMPI then_branch
    
    else_branch:
        PUSH 0
        STORE y
        JUMP end
    
    then_branch:
        PUSH 1
        STORE y
    
    end:
        STOP
    """
    return assemble(source)
