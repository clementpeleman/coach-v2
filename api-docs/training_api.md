GARMIN INTERNATIONAL

Garmin Connect Developer
Program
Training API V2
Version 1.0
CONFIDENTIAL

1 Revision History

Version

1.0

Date

Revisions

05/26/2025

Initial version

Contents

1 Revision History ...................................................................................................................................... 2
2 Getting Started ....................................................................................................................................... 4
2.1 Purpose of the API ...................................................................................................................... 4
2.2 Consumer Key and Secret .......................................................................................................... 4
2.3 User Registration ........................................................................................................................ 4
2.4 Training API Import Types .......................................................................................................... 5
2.5 Requesting a Production Key ..................................................................................................... 5
2.6 API Rate Limiting or Excessive Usage ....................................................................................... 6
3 Training API Endpoint Details .................................................................................................................. 7
3.1 Training API Permissions............................................................................................................ 7
3.2 Workouts ..................................................................................................................................... 8
3.2.1 Field Definitions ....................................................................................................................................... 8

3.2.2 Example JSON ........................................................................................................................................ 14

3.2.3 Create .................................................................................................................................................... 21

3.2.4 Retrieve .................................................................................................................................................. 21

3.2.5 Update ................................................................................................................................................... 21

3.2.6 Delete .................................................................................................................................................... 21

3.2.7 Response Code ....................................................................................................................................... 21
3.3 Workout Schedules ................................................................................................................... 22
3.3.1 Field Definitions ..................................................................................................................................... 22

3.3.2 Example JSON ........................................................................................................................................ 22

3.3.3 Create .................................................................................................................................................... 22

3.3.4 Retrieve .................................................................................................................................................. 22

3.3.5 Update ................................................................................................................................................... 22

3.3.6 Delete .................................................................................................................................................... 23

3.3.7 Retrieve by Date .................................................................................................................................... 23

3.3.8 Response Code ....................................................................................................................................... 23

2 Getting Started

2.1 Purpose of the API

The Garmin Connect Training API is the underlying mechanism that allows users to
import workouts and workout schedules from third-party platforms for supported
activity types into their Garmin Connect account, making it easy to manage this type of
information in a centralized location.

Support Email: connect-support@developer.garmin.com

2.2 Consumer Key and Secret

Garmin Connect Training API partners will be provided with a consumer key and secret,
which will be used to gain access to the Training API. The consumer key is used to
identify a partner’s app uniquely, and the consumer secret is used to validate that the
requests received are from that partner and not from a third party that has gained
unauthorized access to the consumer key. The consumer key can be considered public
information, but the consumer secret is private. For the security of users, the
consumer secret should be secured and never sent over a network in plain text.

Consumer key credentials are created using the Developer Portal and the creation of
apps (https://developerportal.garmin.com/user/me/apps?program=829).

Your first app is designed for testing, and the partner must pass the app review to
request a production-level app for commercial use.

-  Please see “Requesting a Production Key” below for more information.

-  Evaluation-level apps violating API guidelines may be disabled with no prior

notice.

2.3 User Registration

Before a partner can write data to a user’s account, the user must grant the partner write
access. Please refer to the detailed Garmin OAuth documentation for details on acquiring,
authorizing, and signing with a User Access Token (UAT) to write data to a Garmin user’s
account.

2.4 Training API Import Types

All data uploaded to Garmin Connect via the Training API can either be categorized as a
workout or a workout schedule. The API allows for the standard CRUD operations on
these two data types.

•  Workout

A workout contains a list of steps for the user to take as part of their workout, as well as
metadata about the workout (e.g. description, sport type, etc.).

•

 Workout Schedule

A workout schedule allows a previously defined workout to be scheduled for a specified
day.

2.5 Requesting a Production Key

The first consumer key generated through the Developer Portal is an evaluation key. This
key is rate-limited and should only be used for testing, evaluation, and development. To
receive production-level credentials, Garmin must review and approve the Training API
integration to ensure high-quality user experience in Garmin Connect. Garmin will also
review partner applications and/or websites to ensure proper usage of Garmin assets
(e.g., device images, logos) and adherence to Garmin brand guidelines.

Please email Training API support at connect-support@developer.garmin.com  to
request and schedule a production readiness review.

Garmin will review the following technical review:

•  Authorization for at least two Garmin Connect users.

•  User Deregistration/User Permission Endpoints enabled.

•  No unnecessary or excessive API call utilization or volume.

•  Proper handling of quota violations and subsequent retry attempts.

User experience review. This review can be achieved through a demonstration
application to Garmin via video conference or other mutually agreed-upon method. This
review is used to confirm that the following criteria are met:

•  Proper representation of all Garmin trademarked/copyrighted terms.

•  Proper representation of Garmin products and product images.

•  The user experience (UX) flow does not misrepresent Garmin or portray it in a

negative light.

2.6 API Rate Limiting or Excessive Usage

To manage capacity and ensure system stability, Garmin Training API implementations
may be subject to rate limiting.

Please plan the implementation with the following limitations in mind:

Evaluation Rate Limits

100 API call requests per partner per minute - a rolling 60 second window summing the
Oauth requests and API calls.

200 API call requests per user per day - a rolling 24‐hour window excluding Oauth
requests.

Production Rate limits

3000 API call requests per partner per minute - a rolling 60 second window summing the
Oauth requests and API calls.

1000 API call requests per user per day - a 24-hour window rolling excluding Oauth
requests.

If one or both above limits are exceeded by a partner or a specific user, the subsequent
API call request attempts will receive an HTTP Status Code 429 (too many requests). The
calls in question will need to be attempted again later.

3 Training API Endpoint Details

3.1 Training API Permissions

Consumers can have multiple permissions like “Activity Export” and “Workout Import”
set up with GC. Users, while signing up may only opt in for fewer permissions, so this
endpoint helps in fetching the permissions for that particular user.

Method & URL: GET https://apis.garmin.com/userPermissions/

Response body: The retrieved user permissions in JSON.

Example response for this endpoint:

{[ "WORKOUT_IMPORT"]}

Users can change their permission after the permission at their Garmin Connect account
settings; Partners will be notified via the User Permission summary Endpoint (see Start
Guide, section 2.6.3 for the summary description)

3.2 Workouts

3.2.1 Field Definitions

Multisport workouts have a limit of 25 segments (25 individual sports) and 250 steps overall. Single sport
workout (one segment) has a limit of 100 steps.

List of devices supporting each workout sport types
https://support.garmin.com/en-US/?faq=lLvhWrmlMv0vGmyGpWjOX6

Data Type

Description

Workout

workoutId

ownerId

workoutName

description

Long

Long

String

String

updatedDate

String

createdDate

String

A unique identifier for the Workout. This field is not
necessary for the Create action and will be set
automatically.

A unique identifier for the owner of the Workout. This
field is not necessary for Creating workouts but is
required for updates.

The name of the Workout.

A description of the Workout with a maximum length of
1024 characters. Longer descriptions will be truncated.

A datetime representing the last update time of the
Workout, formatted as YYYY-mm-dd. Example: "2019-
01-14T16:25:10.0”. This field is not necessary for Create
or Update actions and will be set automatically.

A datetime representing the creation time of the
Workout, formatted as YYYY-mm-dd. Example: "2019-
01-14T16:25:10.0”. This field is not necessary for
Create or Update actions and will be set automatically.

sport

String

The type of sport.

estimatedDurationInSecs

Integer

estimatedDistanceInMeters

Double

Multi Sport workouts: MULTI_SPORT

Single Segment (sport) workouts: RUNNING, CYCLING,
LAP_SWIMMING, STRENGTH_TRAINING,
CARDIO_TRAINING, GENERIC (supported by some devices
only), YOGA, PILATES

The estimated duration of the Workout in seconds. This
value is calculated server-side and will be ignored in
Create and Update actions.

The estimated distance of the Workout in meters. This
value is  calculated server-side and will be ignored in
Create and Update actions.

poolLength

Double

The length of the pool. Used for when LAP_SWIMMING
segment is present.

poolLengthUnit

workoutProvider

workoutSourceId

String

String

String

isSessionTransitionEnabled  Boolean

Pull Length can be null for undefined pulls (not all devices
support undefined pool, see Appendix C)

The unit of the pool length. Valid values: YARD, METER.

The workout provider to display to the user (20
characters max).

The workout provider to use for internal tracking
purposes. This value should be the same as
workoutProvider unless otherwise noted (20 characters
max).

Must be set to true if workouts should have transitions
for multisport workouts.

Segment

List<Segments>  A list of Segments (individual sports) that specify the

details of the workout.

Segment

segmentOrder

sport

Data Type

Description

Integer

String

estimatedDurationInSecs

Integer

estimatedDistanceInMeters

Double

poolLength

Double

poolLengthUnit

String

Represents the order of the Segments (individual sport)

The type of sport.

Valid values: RUNNING, CYCLING, LAP_SWIMMING,
STRENGTH_TRAINING, CARDIO_TRAINING, GENERIC
(supported by some devices only), YOGA, PILATES

The estimated duration of the Segment in seconds. This
value is calculated server-side and will be ignored in Create
and Update actions.

Will be set to null for single segments workouts

The estimated distance of the Segment in meters. This
value is  calculated server-side and will be ignored in
Create and Update actions.

Will be set to null for single segments workouts

The length of the pool. Used for LAP_SWIMMING.
Must match poolLenght provided in the Workout section
for Multi Sport workouts.

Will be set to null for single segments workouts
(see examples below)

The unit of the pool length. Valid values: YARD, METER.
Must match poolLenght provided in the Workout section
for Multi Sport workouts.

Will be set to null for single segments workouts
(see examples below)

steps

List<Step>

A list of Steps that specify the details of the workout.

WorkoutStep

Data Type

Description

type

String

stepId

Long

The type of Step. Valid values are WorkoutStep and
WorkoutRepeatStep. WorkoutStep type Steps contains
details of the Step itself, while workoutRepeatSteps
contain a sub-list of Steps that should be repeated until a
condition is met as specified in the repeatType and
repeatValue field.

A unique ID is generated for Step. This value is calculated
server-side and will be ignored in Create actions.

stepOrder

Integer

Represents the order of the Step.

repeatType

String

repeatValue

Double

skipLastRestStep

Boolean

steps

List<Step>

intensity

String

description

String

durationType

String

The type of repeat action specifies how long or until
when the user should repeat the sub-list of Steps. Used
only for WorkoutRepeatSteps. Valid values:
REPEAT_UNTIL_STEPS_CMPLT, REPEAT_UNTIL_TIME,
REPEAT_UNTIL_DISTANCE, REPEAT_UNTIL_CALORIES,
REPEAT_UNTIL_HR_LESS_THAN,
REPEAT_UNTIL_HR_GREATER_THAN,
REPEAT_UNTIL_POWER_LESS_THAN,
REPEAT_UNTIL_POWER_GREATER_THAN,
REPEAT_UNTIL_POWER_LAST_LAP_LESS_THAN,
REPEAT_UNTIL_MAX_POWER_LAST_LAP_LESS_THAN

The value of repeating action. When paired with
repeatType, specifies how long or until when the user
should repeat the sub list of steps. Used only for
WorkoutRepeatSteps.

Flag to support Garmin Connect Skip Rest step feature. Set to
true automatically for all LAP_SWIMMING workouts to support
backward compatibility.

The list of steps that should be repeated as specified by
repeatType and repeatValue. Used only for
WorkoutRepeatSteps.

The  intensity  of  the  Step.  Valid  values:  REST,  WARMUP,
COOLDOWN, RECOVERY, ACTIVE, INTERVAL, MAIN (SWIM
only)

A description of the Step with a maximum of 512
characters. Longer descriptions will be truncated.

The  type  of  duration.  Paired  with  durationValue,  this
represents  the relative duration of the Step. Valid values:
TIME, DISTANCE, HR_LESS_THAN, HR_GREATER_THAN,
CALORIES, OPEN, POWER_LESS_THAN,
POWER_GREATER_THAN, TIME_AT_VALID_CDA,
FIXED_REST (for rest steps)

REPS (HIIT, CARDIO, STRENGH_TRSINING only)

equipmentType

String

exerciseCategory

String

exerciseName

String

LAP_SWIMMING ONLY:
FIXED_REST (should be used for REST In LAP_SWIMMING)
REPETITION_SWIM_CSS_OFFSET (CSS-Based Send-Off
Time) valid values -60 to 60)
FIXED_REPETITION (Send-off time)
Please note "poolLengthUnit" must be set with the use of send-
off time.

The type of equipment needed for this Step. Currently used
only for LAP_SWIMMING Workouts. Valid values: NONE,
SWIM_FINS, SWIM_KICKBOARD, SWIM_PADDLES,
SWIM_PULL_BUOY, SWIM_SNORKEL

The  exercise  category  for  this  Step.  Used  only  for
STRENGTH_TRAINING and CARDIO_TRAINING, HIIT,
PILATES, and YOGA Workouts.
Valid values:  See Appendix A and B.(excel file)

The exercise name for this Step. Used only for
STRENGTH_TRAINING and CARDIO_TRAINING, HIIT,
PILATES, and YOGA Workouts.

See Appendix A and B (excel file)

weightValue

Double

The weight value for this step is kilograms. Used only for
STRENGTH_TRAINING Workouts.

weightDisplayUnit

String

The units in which to display the weightValue to the
user, if a weightValue exists. The display unit does not
impact weightValue within the Training API, only for
display. Valid values: KILOGRAM, POUND

durationValue

Double

The duration value. Pair with durationType, this
represents the relative duration of the Step.

durationValueType

String

A modifier for duration value is used only for HR and
POWER,  types to express units. Valid values: PERCENT

targetType

String

The type of target for this Step. Valid values: SPEED,
HEART_RATE, CADENCE, POWER, GRADE, RESISTANCE,
POWER_3S, POWER_10S, POWER_30S, POWER_LAP,
SPEED_LAP, HEART_RATE_LAP, OPEN
PACE (as speed in m/s)

Please note that targetType is not supported for swim
workouts. Please set targetType as null for swim

targetValue

Double

workouts
Use PAZE_ZONE as the secondary target for swim
workouts.

OPEN – if using secondary target, this value cannot be set as
targetType.

The target HR (valid values 1-5) or power zone (valid
values 1-7) to be used for this Step. Target zones must
have been previously defined and saved.

targetValueLow

Double

The lowest value for the target range. Used to specify a
custom range instead of specifying a target zone through
targetValue.

targetValueHigh

Double

The highest value for the target range. Used to specify a
custom range instead of specifying a target zone through
targetValue.

targetValueType

String

A modifier for target value is used only for HR and POWER
types to express units. Valid values: PERCENT

secondaryTargetType*

String

secondaryTargetValue*

Double

secondaryTargetValueLow*  Double

The type of target for this Step. Valid values: SPEED,
HEART_RATE,  OPEN, CADENCE, POWER, GRADE,
RESISTANCE, POWER_3S, POWER_10S, POWER_30S,
POWER_LAP, SPEED_LAP, HEART_RATE_LAP,
PACE (as speed in m/s)

LAP_SWIMMING WORKOUT only:

1.  SWIM_INSTRUCTION (Text-based Intensity target)
2.  SWIM_CSS_OFFSET

PACE_ZONE (in m/s)

The target HR (valid values 1-5) or power zone (valid
values 1-7) is to be used for this Step. Target zones must
have been previously defined and saved.

The lowest value for the target range. Used to specify a
custom range instead of specifying a target zone through
targetValue.

LAP_SWIMMING:

SWIM_INSTRUCTION valid values: 1- 10

1 -RECOVERY
2 -VERY EASY
3 -EASY
4 -MODERATE
5 -HARD

6 -VERY_HARD
7 -ALL_OUT
8 -FAST
9 -ASCEND
10 -DESCEND

SWIM_CSS_OFFSET (CSS-Based Target Pace) valid value:  -60
to 60
(seconds)

PACE_ZONE

Provide value in m/s
0.8333333333333334 device with the metric system shown as
2:00/100

The highest value for the target range. Used to specify a
custom range instead of specifying a target zone through
targetValue.

secondaryTargetValueHigh*  Double

secondaryTargetValueType*  String

A modifier for target value is used only for HR and POWER
types to express units.

strokeType

String

drillType

String

equipmentType

String

exerciseCategory

String

exerciseName

String

The type of stroke for this Step. Used only in
LAP_SWIMMING Workouts.
Valid values: BACKSTROKE, BREASTSTROKE,
BUTTERFLY, FREESTYLE, MIXED, IM, RIMO, CHOICE

The type of drill for this Step. Used only in
LAP_SWIMMING Workouts.
Valid values: KICK, PULL, BUTTERFLY

The type of equipment needed for this Step. Currently used
only for LAP_SWIMMING Workouts. Valid values: NONE,
SWIM_FINS, SWIM_KICKBOARD, SWIM_PADDLES,
SWIM_PULL_BUOY, SWIM_SNORKEL

The  exercise  category  for  this  Step.  Used  only  for
STRENGTH_TRAINING, YOGA, and CARDIO_TRAINING
Workouts.
Valid values:  See Appendix A and B.

The exercise name for this Step. Used only for
STRENGTH_TRAINING and CARDIO_TRAINING, HIIT,
PILATES, and YOGA Workouts.

See Appendix A for the list of exercise names for YOGA and
PILATES

See Appendix B for the list of exercise names for
STRENGTH_TRAINING and CARDIO_TRAINING, HIIT

weightValue

Double

The weight value for this step is kilograms. Used only for
STRENGTH_TRAINING Workouts.

weightDisplayUnit

String

The units in which to display the weightValue to the
user, if a weightValue exists. The display unit does not
impact weightValue within the Training API, only for
display. Valid values: KILOGRAM, POUND

List of supported devices for CYCLING secondary target https://support.garmin.com/en-
US/?faq=EMMh03mfYU59Zt0ldOw0U6

The secondary target is valid for:

1.  CYCLING and should be treated as a less formal, accessory target. The target type
for a secondary target should be different from the primary target. If secondary
target is used, OPEN cannot be used as first target.

2.  Secondary is also supported for SWIM workouts to provide a text-based target,

pace, CSS-based target pace (see Appendix C for additional details)

** Swim workouts should be distance-based and if there is a repeat block with rest as a
step included, an extra repeat step should be added after the repeat block because the
device will skip the last rest step in the repeat block.

3.2.2 Example JSON

MULTI_SPORT:
{
  "ownerId": 12345,
  "workoutName": "TEST",
  "description": "TEST",
  "sport": "MULTI_SPORT",
  "estimatedDurationInSecs": 1200,
  "estimatedDistanceInMeters": 1400,
  "poolLength": null,
  "poolLengthUnit": null,
  "workoutProvider": "multipsport",
  "workoutSourceId": "multisport",
  "isSessionTransitionEnabled": true,
  "segments": [
    {
      "segmentOrder": 1,

      "sport": "CYCLING",
      "poolLength": null,
      "poolLengthUnit": null,
      "estimatedDurationInSecs": 500,
      "estimatedDistanceInMeters": 500,
      "steps": [
        {
          "type": "WorkoutStep",
          "stepOrder": 1,
          "intensity": "ACTIVE",
          "description": "",
          "durationType": "DISTANCE",
          "durationValue": 1000,
          "durationValueType": "METER",
          "targetType": "OPEN",
          "targetValue": null,
          "targetValueLow": null,
          "targetValueHigh": null,
          "targetValueType": null,
          "secondaryTargetType": null,
          "secondaryTargetValue": null,
          "secondaryTargetValueLow": null,
          "secondaryTargetValueHigh": null,
          "secondaryTargetValueType": null,
          "strokeType": null
          "drillType": null,
          "equipmentType": null
          "exerciseCategory": null,
          "exerciseName": null,
          "weightValue": null,
          "weightDisplayUnit": null
        },
        {
          "type": "WorkoutRepeatStep",
          "stepOrder": 2,
          "repeatType": "REPEAT_UNTIL_STEPS_CMPLT",
          "repeatValue": 4,
          "steps": [
            {
              "type": "WorkoutStep",
              "stepOrder": 3,
              "intensity": "ACTIVE",
              "description": null,
              "durationType": "DISTANCE",
              "durationValue": 100,
              "durationValueType": "METER",
              "targetType": null,
              "targetValue": null,
              "targetValueLow": null,
              "targetValueHigh": null,

              "targetValueType": null,
              "secondaryTargetType": null,
              "secondaryTargetValue": null,
              "secondaryTargetValueLow": null,
              "secondaryTargetValueHigh": null,
              "secondaryTargetValueType": null,
              "strokeType": null,
              "equipmentType": null,
              "exerciseCategory": null,
              "exerciseName": null,
              "weightValue": null,
              "weightDisplayUnit": null
            }
          ]
        }
      ]
    },
    {
      "segmentOrder": 2,
      "sport": "RUNNING",
      "poolLength": null,
      "poolLengthUnit": null,
      "estimatedDurationInSecs": null,
      "estimatedDistanceInMeters": null,
      "steps": [
        {
          "type": "WorkoutStep",
          "stepOrder": 4,
          "intensity": "ACTIVE",
          "description": "",
          "durationType": "DISTANCE",
          "durationValue": 1000,
          "durationValueType": "METER",
          "targetType": "OPEN",
          "targetValue": null,
          "targetValueLow": null,
          "targetValueHigh": null,
          "targetValueType": null,
          "secondaryTargetType": null,
          "secondaryTargetValue": null,
          "secondaryTargetValueLow": null,
          "secondaryTargetValueHigh": null,
          "secondaryTargetValueType": null,
          "strokeType": null,
          "drillType": null,
          "equipmentType": null,
          "exerciseCategory": null,
          "exerciseName": null,
          "weightValue": null,
          "weightDisplayUnit": null

        },
        {
          "type": "WorkoutRepeatStep",
          "stepOrder": 5,
          "repeatType": "REPEAT_UNTIL_STEPS_CMPLT",
          "repeatValue": 4,
          "steps": [
            {
              "type": "WorkoutStep",
              "stepOrder": 6,
              "intensity": "ACTIVE",
              "description": null,
              "durationType": "DISTANCE",
              "durationValue": 100,
              "durationValueType": "METER",
              "targetType": null,
              "targetValue": null,
              "targetValueLow": null,
              "targetValueHigh": null,
              "targetValueType": null,
              "secondaryTargetType": null,
              "secondaryTargetValue": null,
              "secondaryTargetValueLow": null,
              "secondaryTargetValueHigh": null,
              "secondaryTargetValueType": null,
              "strokeType": null,
              "equipmentType": null,
              "exerciseCategory": null,
              "exerciseName": null,
              "weightValue": null,
              "weightDisplayUnit": null
            }
          ]
        }
      ]
    }
  ]
}

SINGLE Segment (one sport type)
{
  "ownerId": 12345,
  "workoutName": "TEST",
  "description": "TEST",
  "sport": "CYCLING",
  "estimatedDurationInSecs": 1200,
  "estimatedDistanceInMeters": 1400,
  "poolLength": null,
  "poolLengthUnit": null,

  "workoutProvider": "single_segemnt",
  "workoutSourceId": "single_segemnt",
  "isSessionTransitionEnabled": false,
  "segments": [
    {
      "segmentOrder": 1,
      "sport": "CYCLING",
      "poolLength": null,
      "poolLengthUnit": null,
      "estimatedDurationInSecs": 500,
      "estimatedDistanceInMeters": 500,
      "steps": [
        {
          "type": "WorkoutStep",
          "stepOrder": 1,
          "intensity": "ACTIVE",
          "description": "",
          "durationType": "DISTANCE",
          "durationValue": 1000,
          "durationValueType": "METER",
          "targetType": "OPEN",
          "targetValue": null,
          "targetValueLow": null,
          "targetValueHigh": null,
          "targetValueType": null,
          "secondaryTargetType": null,
          "secondaryTargetValue": null,
          "secondaryTargetValueLow": null,
          "secondaryTargetValueHigh": null,
          "secondaryTargetValueType": null,
          "strokeType": null,
          "drillType": null,
          "equipmentType": null,
          "exerciseCategory": null,
          "exerciseName": null,
          "weightValue": null,
          "weightDisplayUnit": null
        },
        {
          "type": "WorkoutRepeatStep",
          "stepOrder": 2,
          "repeatType": "REPEAT_UNTIL_STEPS_CMPLT",
          "repeatValue": 4,
          "steps": [
            {
              "type": "WorkoutStep",
              "stepOrder": 3,
              "intensity": "ACTIVE",
              "description": null,
              "durationType": "DISTANCE",

              "durationValue": 100,
              "durationValueType": "METER",
              "targetType": null,
              "targetValue": null,
              "targetValueLow": null,
              "targetValueHigh": null,
              "targetValueType": null,
              "secondaryTargetType": null,
              "secondaryTargetValue": null,
              "secondaryTargetValueLow": null,
              "secondaryTargetValueHigh": null,
              "secondaryTargetValueType": null,
              "strokeType": null,
              "equipmentType": null,
              "exerciseCategory": null,
              "exerciseName": null,
              "weightValue": null,
              "weightDisplayUnit": null
            },

{

          "type": "WorkoutStep",
          "stepOrder": 4,
          "intensity": "ACTIVE",
          "description": "",
          "durationType": "DISTANCE",
          "durationValue": 1000,
          "durationValueType": "METER",
          "targetType": "OPEN",
          "targetValue": null,
          "targetValueLow": null,
          "targetValueHigh": null,
          "targetValueType": null,
          "secondaryTargetType": null,
          "secondaryTargetValue": null,
          "secondaryTargetValueLow": null,
          "secondaryTargetValueHigh": null,
          "secondaryTargetValueType": null,
          "strokeType": null,
          "drillType": null,
          "equipmentType": null,
          "exerciseCategory": null,
          "exerciseName": null,
          "weightValue": null,
          "weightDisplayUnit": null
        },
        {
          "type": "WorkoutRepeatStep",
          "stepOrder": 5,
          "repeatType": "REPEAT_UNTIL_STEPS_CMPLT",
          "repeatValue": 4,

          "steps": [
            {
              "type": "WorkoutStep",
              "stepOrder": 6,
              "intensity": "ACTIVE",
              "description": null,
              "durationType": "DISTANCE",
              "durationValue": 100,
              "durationValueType": "METER",
              "targetType": null,
              "targetValue": null,
              "targetValueLow": null,
              "targetValueHigh": null,
              "targetValueType": null,
              "secondaryTargetType": null,
              "secondaryTargetValue": null,
              "secondaryTargetValueLow": null,
              "secondaryTargetValueHigh": null,
              "secondaryTargetValueType": null,
              "strokeType": null,
              "equipmentType": null,
              "exerciseCategory": null,
              "exerciseName": null,
              "weightValue": null,
              "weightDisplayUnit": null
                }
              ]
             }
           ]
         }
        ]
     }
  ]
}

3.2.3 Create
This request is to create a workout by/for a user:

Method & URL: POST https://apis.garmin.com/workoutportal/workout/v2

Request body: The new workout in JSON. A workout ID should not be included.

Content-Type: application/json

Response Body: The newly created workout as JSON.

3.2.4 Retrieve
This request is to retrieve a workout by/for a user:

Method & URL: GET https://apis.garmin.com/training-api/workout/v2/{workoutId}

Response body: The retrieved workout in JSON.

3.2.5 Update
This request is to update a workout by/for a user:

Method & URL: PUT https://apis.garmin.com/training-api/workout/v2/{workoutId}

Request body: The full updated workout in JSON.

Content-Type: application/json

3.2.6 Delete
This request is to delete a workout by/for a user:

Method & URL: DELETE https://apis.garmin.com/training-api/workout/v2/{workoutId}

3.2.7 Response Code

HTTP Response Status

Description

200/204

Workout successfully created

400

401

403

412

429

Bad Request

User Access Token doesn’t exist

Not allowed

User Permission error

Quota violation / rate‐limiting

3.3 Workout Schedules

3.3.1 Field Definitions

Filed Name

scheduleId
workoutId

date

Description
A unique identifier for the workout schedule
The ID of the workout to which the schedule
refers
The schedule data, formatter as
‘YYYY-mm-dd’

3.3.2 Example JSON
{
"scheduleId":123, "workoutId":123, "date":"2019-01-31"
}

3.3.3 Create
This request is to create a workout schedule by/for a user:

Method & URL: POST https://apis.garmin.com/training-api/schedule/

Request body: A workout schedule to create. A schedule Id should not be included.

Content-Type: application/json

3.3.4 Retrieve
This request is to retrieve a workout schedule by/for a user:

Method & URL:

 GET https://apis.garmin.com/training-api/schedule/{workoutScheduleId}

Response body: The retrieved workout schedule

3.3.5 Update
This request is to update a workout schedule by/for a user:

Method & URL:

PUT https://apis.garmin.com/training-api/schedule/{workoutScheduleId}

Request body: The full workout schedule in JSON.

Content-Type: application/json

Response body: The updated workout schedule.

3.3.6 Delete
This request is to delete a workout schedule by/for a user:
Method & URL:

DELETE https://apis.garmin.com/training-api/schedule/{workoutScheduleId}

3.3.7 Retrieve by Date

This request is used to retrieve the workout schedule by/for a user by date range:

Method & URL:

GET https://apis.garmin.com/training-api/schedule?startDate=YYYY-mm-
dd&endDate=YYYY-mm-dd

3.3.8 Response Code

HTTP Response Status

Description

200/204

Workout successfully created

400

401

403

412

429

Bad Request

User Access Token doesn’t exist

Not allowed

User Permission error

Quota violation / rate‐limiting

Appendix C.

Garmin Connect Swim improvements feature overview

This is an overview of all changes for the Training API and swim workouts 2024

Improvement

JSON/comments

Support for 100 workout steps for all sport
types
(except Forerunner 935 generation and
older, Fenix 5 generation and older)

Handling pool size mismatches on devices.
If your pool size provided via API differs
from the pool size set on the watch, users
are given the option on your device to
convert the workout and do it anyway

“Unspecified” pool size support.
Workouts created with unspecified pool
sizes can be completed in any size of the
pool. The step distances specified in the
workout are shown on the device without
conversion.

"poolLength" : null,
"poolLengthUnit": null
Please note "poolLengthUnit" must be set
using send-off time, CSS-Based Send-Off
Time, and pace secondary target. Valid
values: YARD, METER

Swim target supported as secondary target
(no primary target must be specified)
Text-based Intensity target
CSS (valid values -60 to 60)
Pace is officially supported as a secondary
target

"targetType": null,
"secondaryTargetType":
"SWIM_INSTRUCTION",
"secondaryTargetValueLow": "RECOVERY"

"targetType": null,
"secondaryTargetType":
"SWIM_CSS_OFFSET",
"secondaryTargetValueLow": -5,

"targetType": null,
"secondaryTargetType": "PACE_ZONE",
"secondaryTargetValueLow":
0.5555555555555556 (the number needs
to be provided in m/s)

Please note "poolLengthUnit" must be set
using send-off time and pace secondary

New drill types (“Kick”, “Pull”, and “Drill”)
are shown separately from the stroke type
on the user's device. E.g. “Free Pull” or
“Butterfly Kick”.

New stroke types:
- RIMO (Reverse IM order)
- IM by Round
- Choice

New Step Intensity
 - Main

target. Valid values: YARD, METER

"strokeType": "BUTTERFLY"
"drillType": "KICK"
(targetType will is not supported with use
of strokeType, please use secondary target
to specify targets).

"strokeType": "RIMO"

"intensity": "MAIN"

New Duration types for Swim Rest Step
added: CSS-Based Send-Off Time and Send-
off time
Send-off times and target paces defined
relative to your CSS will automatically
adjust when your CSS changes. Default CSS
is 2:00 / 100 m.

REPETITON_SWIM_CSS_OFFSET (CSS-
Based Send-Off Time) valid values -60 to 60
FIXED_REPETITION (Send-off time)
Please note "poolLengthUnit" must be set
with use of send-off time and pace
secondary target. Valid values: YARD,
METER

skipLastRestStep

Time-Based steps support. On the device,
an alert sounds when the target time has
elapsed. Continue swimming to the wall
and press Lap to advance to the next step.

 Optional Flag to support Garmin Connect
Skip Rest step feature. Set to true for all
LAP_SWIMMING workout to support
backward compatibility.

Range:  1 minute - 59 minutes.


