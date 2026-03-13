# Chakravyuh — User Flow Diagram
This document outlines the exact flow of the game from the player's perspective. It explains the core gameplay loop, the choices they make, the consequences of those choices, and how they ultimately win or lose.

## The Player's Journey

```mermaid
flowchart TD
    %% -- Entry Point --
    Start((Player Clicks\n"Start Game"))
    
    %% -- Stage 1: Initialization --
    subgraph Stage1 [Stage 1: Identity Assignment]
        direction TB
        GenPersona[🎲 The game assigns you a random Persona\ne.g., ₹45,000 Income, 'FOMO' Weakness]
        InitBank[� Your Bank Account starts with\n1 Month's Salary]
        GenPersona --> InitBank
    end

    %% -- Stage 2: The Action Phase --
    subgraph Stage2 [Stage 2: The Monthly Scenario]
        direction TB
        ShowScenario[📱 A Personalized Emergency or Temptation Appears\nTailored to your current cash and weakness]
        WaitChoice{🤔 You Must Choose\nExactly One Option}
        
        ChoiceA[1️⃣ Pay Cash\nThe Safe Drain]
        ChoiceB[2️⃣ Buy Now, Pay Later\nThe EMI Trap]
        ChoiceC[3️⃣ Ignore It\nThe Stress Spike]

        ShowScenario --> WaitChoice
        WaitChoice --> ChoiceA
        WaitChoice --> ChoiceB
        WaitChoice --> ChoiceC
    end

    %% -- Stage 3: The Consequences --
    subgraph Stage3 [Stage 3: The Consequences]
        direction TB
        ApplyConsequence[⚙️ Month advances: Rent is paid, EMIs deducted]
        CashCheck{💸 Do you have\nNegative Cash?}
        
        DebtSpiral[🚨 The Debt Spiral Hits\nYou are charged ₹1,500 Overdraft Fee\nand gain +15 Mental Stress]
        
        ApplyConsequence --> CashCheck
        CashCheck -- "Yes, below zero" --> DebtSpiral
    end

    %% -- Stage 4: Evaluation --
    subgraph Stage4 [Stage 4: Win or Lose?]
        direction TB
        LossCondition{Is Stress >= 100?}
        WinCondition{Is it Month 12?}
    end

    %% -- End States --
    GameOverWin((🏆 VICTORY\nAuditor gives you a\nSurvival Report))
    GameOverLoss((💀 MENTAL BREAKDOWN\nAuditor explains how the\nDebt Spiral broke you))

    %% -- Flow Connections --
    Start --> GenPersona
    InitBank --> ShowScenario
    
    ChoiceA -- "- Cash instantly" --> ApplyConsequence
    ChoiceB -- "+ Hidden 24% Debt" --> ApplyConsequence
    ChoiceC -- "+ 25 Stress instantly" --> ApplyConsequence
    
    CashCheck -- "No, still positive" --> LossCondition
    DebtSpiral --> LossCondition

    LossCondition -- "Yes" --> GameOverLoss
    LossCondition -- "No" --> WinCondition

    WinCondition -- "Yes" --> GameOverWin
    WinCondition -- "No, keep playing" --> ShowScenario
```

## How to Explain the Game Flow to Judges

1. **The Setup**: It's a 12-month survival game. You are randomly assigned an income and a psychological weakness (like FOMO or Guilt).
2. **The Hook**: Every month, our AI studies your bank balance and your weakness, and throws a highly personalized trap at you.
3. **The Trilemma**: You always have exactly 3 bad choices: drain your cash right now, get trapped in a high-interest EMI, or ignore the problem and take a massive hit to your mental stress.
4. **The Punishment (Debt Spiral)**: If your cash dips below zero, you don't instantly lose. Instead, you enter a terrifying debt spiral where the game slaps you with overdraft fees and +15 stress every single month you remain broke.
5. **The Climax**: The game ends when you either survive 12 months, or your stress hits 100 and you suffer a mental breakdown. At the end, our AI Auditor reads your transaction history and gives you a brutal, highly educational report on the exact mistakes you made.
