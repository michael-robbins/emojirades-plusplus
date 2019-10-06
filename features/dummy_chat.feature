@spike
Feature: Dummy Chats
  2 dummies talking to each other

  Scenario: Knock Knock
    Given Robbins is online
    And Dave is online
    When Robbins says "knock knock"
    Then Dave says "who's there"