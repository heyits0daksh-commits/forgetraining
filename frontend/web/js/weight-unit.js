'use strict';

// ============================================================
// WEIGHT UNIT (display-only) — every weight the backend returns or the
// app stores (working_weight_kg, biometrics, logged sets, history) stays
// in kg exactly as load_prescription.py and the payload schema expect.
// This only changes how a kg number is *shown* and how a number the user
// *types* into a "logged weight" box is interpreted before it's turned
// back into kg for storage - so PRs stay comparable across unit switches.
// ============================================================

var UNIT_KEY = 'forge_unit';
var KG_PER_LB = 0.45359237;
function loadUnit(){
  try{ return localStorage.getItem(UNIT_KEY) === 'lb' ? 'lb' : 'kg'; }catch(e){ return 'kg'; }
}
function kgToLb(kg){ return kg / KG_PER_LB; }
function lbToKg(lb){ return lb * KG_PER_LB; }
var CM_PER_IN = 2.54;
function cmToIn(cm){ return cm / CM_PER_IN; }
function inToCm(inches){ return inches * CM_PER_IN; }
// Formats a kg value already computed by the backend/app for display.
function fmtWeight(kg){
  if(kg == null) return kg;
  return (S.unit === 'lb' ? Math.round(kgToLb(kg)) : kg) + (S.unit === 'lb' ? 'lb' : 'kg');
}
// Converts a value the user just typed in a "log this set's weight" box
// (shown in whichever unit is currently active) into kg before it's
// scored or stored - internal storage is always kg, unit only affects
// what's on screen.
function inputToKg(value){
  return S.unit === 'lb' ? lbToKg(value) : value;
}
// The biometrics fields (bioWeight/bioBench/bioSquat/bioDeadlift and their
// pgBio* counterparts) are unit-converted in place whenever the toggle
// flips (see the unit-weight-input handling in initUnit below), so unlike
// fmtWeight() - which converts a kg value the backend/app computed - these
// numbers are already sitting in whichever unit is currently displayed.
// This just labels them; it must never run them through kgToLb again.
function fmtRawUnit(value){
  if(value == null || isNaN(value)) return value;
  return value + (S.unit === 'lb' ? 'lb' : 'kg');
}

// Each discipline gets a monogram (badge glyph), a native/traditional word
// (shown as a large watermark once the discipline is active) and an accent
// color that tints that whole part of the app — the goal is that picking a
// discipline actually feels like stepping into that sport's world, not just
// selecting an item from a list.
var SPORT_THEME = {
  'Judo':            {mono:'柔', word:'柔道',        region:'Japan',                 accent:'#B33A2E', img:[
    'assets/img/judo.jpg',
    'https://images.unsplash.com/photo-1585537884613-1a9bcd024983?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1515025617920-e1e674b5033c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1514050566906-8d077bae7046?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1676220672943-5100a727ba36?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1525198104776-f6e8a873f9b7?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1555597673-b21d5c935865?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1555597408-26bc8e548a46?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1529630218527-7df22fc2d4ee?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1529566193698-bc394165d541?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1564415315949-7a0c4c73aab4?auto=format&fit=crop&w=900&q=80'
  ]},
  'Wrestling':        {mono:'Π', word:'ΠΆΛΗ',        region:'Ancient Greece',        accent:'#9C7A3C', img:[
    'assets/img/wrestling.jpg',
    'https://images.unsplash.com/photo-1764908912174-cf465d433f0f?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1542468019-550cb643a5e3?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1533777528790-c6996cffa35e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1611338631743-b0362363f417?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1540206235220-7590996b7a5a?auto=format&fit=crop&w=900&q=80'
  ]},
  'Boxing':           {mono:'B', word:'BOXING',      region:'The Sweet Science',     accent:'#A6332B', img:[
    'assets/img/boxing.jpg',
    'https://images.unsplash.com/photo-1765302840608-6c67281260c3?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1495555775484-97f7c56a7ba9?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1546711076-85a7923432ab?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1622599490476-f804e3092019?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1549719386-74dfcbf7dbed?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1552072092-7f9b8d63efcb?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1509563268479-0f004cf3f58b?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1622599511051-16f55a1234d0?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1495555687398-3f50d6e79e1e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1575654402720-0af3480d1fad?auto=format&fit=crop&w=900&q=80'
  ]},
  'Muay Thai':        {mono:'ม', word:'มวยไทย',       region:'Thailand',              accent:'#C9A227', img:[
    'https://images.unsplash.com/photo-1525680996651-0222228be6f0?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1644497876755-03f6869efb4c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1637974013743-82656f7c3f49?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1562679452-763edf60a0b7?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1611816153165-fed23698666d?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1612179736716-d643f0bdcf4e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1601039834076-c41cf1766d4b?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1601588462060-470011bd9a18?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1611816153260-815a15a0993d?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1611824916173-508ca2931d4d?auto=format&fit=crop&w=900&q=80'
  ]},
  'Kickboxing':       {mono:'蹴', word:'キックボクシング', region:'Japan',                 accent:'#8E4A8E', img:[
    'https://images.unsplash.com/photo-1636581563884-39569e81cbad?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1517438322307-e67111335449?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1546711076-85a7923432ab?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1575654402720-0af3480d1fad?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1575747515871-2e323827539e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1607702713064-0143212236ae?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1521800641212-77d98bb90d21?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1611077479643-5b3c01381f9e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1476525223214-c31ff100e1ae?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1526889588514-2e695856df85?auto=format&fit=crop&w=900&q=80'
  ]},
  'Sambo':            {mono:'С', word:'САМБО',       region:'Russia',                accent:'#7C3F3F', img:[
    'https://images.unsplash.com/photo-1777305936039-e205e7d594a3?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1541337082051-5959dbb57d5d?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1680022546558-550eaf22351e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1680022550327-84d2a39c9328?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1619369232549-2deddaf62454?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1680022548963-1d8e630a272b?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1615117950029-db3cf44bdefa?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1680022703849-7d1a79f05ad8?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1615117973420-cce962a65005?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1636391134068-083dd5e3209b?auto=format&fit=crop&w=900&q=80'
  ]},
  'BJJ':              {mono:'J', word:'JIU-JITSU',   region:'Brazil',                accent:'#2E7D46', img:[
    'https://images.unsplash.com/photo-1611711605692-acb25d5d8399?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1682545888368-587f56efd06e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1598300606161-4019d0dfec28?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1656653121475-e33829581294?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1656653121526-a1458317b790?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1571902943202-507ec2618e8f?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1637430308606-86576d8fef3c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1590487988256-9ed24133863e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1623874514711-0f321325f318?auto=format&fit=crop&w=900&q=80'
  ]},
  'Sanda':            {mono:'散', word:'散打',        region:'China',                 accent:'#C77B3E', img:[
    'https://images.unsplash.com/photo-1575800605380-ca1d27744f2c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1539465386388-838f814495bd?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1576678927484-cc907957088c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1550345332-09e3ac987658?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1548690312-e3b507d8c110?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1593079831268-3381b0db4a77?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1577221084712-45b0445d2b00?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1521805103424-d8f8430e8933?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1526889588514-2e695856df85?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1611077479643-5b3c01381f9e?auto=format&fit=crop&w=900&q=80'
  ]},
  'Rugby':            {mono:'R', word:'RUGBY',       region:'Union Football',        accent:'#5C2A2A', img:[
    'https://images.unsplash.com/photo-1574618500275-a5d3458db385?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1480099225005-2513c8947aec?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1508057187925-17094f679b10?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1529663297269-6d349ec39b57?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1558151507-c1aa3d917dbb?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1529478562208-d4c746edcb79?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1676972523246-2ff4125551fb?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1512299286776-c18be8ed6a1a?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1495329356033-eb76e0af9fd9?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1496224027003-38fc92be458c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1485426337939-af69cf101909?auto=format&fit=crop&w=900&q=80'
  ]},
  'Rock Climbing':    {mono:'▲', word:'CLIMB',       region:'Rock & Alpine',         accent:'#5B6B73', img:[
    'https://images.unsplash.com/photo-1601224748193-d24f166b5c77?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1522163182402-834f871fd851?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1577434150790-3bfe143fe4f2?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1597250861267-429663f244a8?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1502126324834-38f8e02d7160?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1564769662533-4f00a87b4056?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1682685796186-1bb4a5655653?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1507034589631-9433cc6bc453?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1516372048654-2e06f99e1382?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1601025678763-e8f5835995db?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1602842900683-0040b9be5dfe?auto=format&fit=crop&w=900&q=80'
  ]},
  'HYROX':            {mono:'H', word:'HYROX',       region:'Hybrid Race',           accent:'#3D6FE0', img:[
    'https://images.unsplash.com/photo-1590556409324-aa1d726e5c3c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1743993414654-0be2b73a9620?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1741562238447-d7c44397f7e0?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1637430308606-86576d8fef3c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1590487988256-9ed24133863e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1576678927484-cc907957088c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1521805103424-d8f8430e8933?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1548690312-e3b507d8c110?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1593079831268-3381b0db4a77?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1571902943202-507ec2618e8f?auto=format&fit=crop&w=900&q=80'
  ]},
  'Special Forces':   {mono:'★', word:'TACTICAL',    region:'Tactical Conditioning', accent:'#55603F', img:[
    'assets/img/special-forces.jpg',
    'https://images.unsplash.com/photo-1700774607216-c37bdeaf9869?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1599058917212-d750089bc07e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1605296867304-46d5465a13f1?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1637430308606-86576d8fef3c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1521805103424-d8f8430e8933?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1576678927484-cc907957088c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1550345332-09e3ac987658?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1593079831268-3381b0db4a77?auto=format&fit=crop&w=900&q=80'
  ]},
  'MMA':              {mono:'M', word:'MMA',         region:'Mixed Martial Arts',    accent:'#3E7CB1', img:[
    'assets/img/mma.jpg',
    'https://images.unsplash.com/photo-1680022702604-292f21514497?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1680022546558-550eaf22351e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1680022550327-84d2a39c9328?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1619369232549-2deddaf62454?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1681203888755-bd61fe3558eb?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1615117972428-28de67cda58e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1680022548963-1d8e630a272b?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1615117950029-db3cf44bdefa?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1680022703849-7d1a79f05ad8?auto=format&fit=crop&w=900&q=80'
  ]},
  'Powerlifting':     {mono:'P', word:'POWERLIFTING', region:'Squat · Bench · Pull',  accent:'#B91C1C', img:[
    'https://images.unsplash.com/photo-1517963879433-6ad2b056d712?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1541534741688-6078c6bfb5c5?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1571902943202-507ec2618e8f?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1637430308606-86576d8fef3c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1590487988256-9ed24133863e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1623874514711-0f321325f318?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1576678927484-cc907957088c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1521805103424-d8f8430e8933?auto=format&fit=crop&w=900&q=80'
  ]},
  'Look Jacked':      {mono:'J', word:'LOOK JACKED',  region:'Built Different',       accent:'#D4AF37', img:[
    'https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1567013127542-490d757e51fc?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1611672585731-fa10603fb9e0?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1571902943202-507ec2618e8f?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1637430308606-86576d8fef3c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1590487988256-9ed24133863e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1623874514711-0f321325f318?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1550345332-09e3ac987658?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1548690312-e3b507d8c110?auto=format&fit=crop&w=900&q=80'
  ]},
  'Strength + Hypertrophy': {mono:'SH', word:'STRENGTH + HYPERTROPHY', region:'5-8 Reps · 70-82%', accent:'#6D4AA6', img:[
    'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1604480133080-602261a680df?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1526506118085-60ce8714f8c5?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1637430308606-86576d8fef3c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1590487988256-9ed24133863e?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1623874514711-0f321325f318?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1576678927484-cc907957088c?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1521805103424-d8f8430e8933?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1550345332-09e3ac987658?auto=format&fit=crop&w=900&q=80',
    'https://images.unsplash.com/photo-1548690312-e3b507d8c110?auto=format&fit=crop&w=900&q=80'
  ]},
  // Not a real discipline - a neutral "no sport" tile so Custom Mode (pick
  // your own exercises) doesn't force picking an actual sport just to
  // satisfy the wizard's "Next" gate. Sport is a free-text field on the
  // backend (WorkoutRequest.sport: str) and every sport-lookup helper in
  // sport_profiles.py already falls back to a neutral default for unknown
  // strings (see blended_transfer_score/movement_emphasis_multiplier), so
  // sending "Custom" needs no backend change - it just gets no sport-specific
  // bias, which is the right behavior when there's no discipline to bias for.
  'Custom':           {mono:'✎', word:'CUSTOM',      region:'',                       accent:'#6B7280'}
};
function themeFor(sport){ return SPORT_THEME[sport] || {mono:(sport||'?').charAt(0).toUpperCase(), word:sport||'', region:'', accent:'var(--red)'}; }
// Which S.emphasis (-> WorkoutRequest.training_emphasis) a discipline tile
// should carry by default, for the two sports that are themselves a
// prescription style rather than a combat/field discipline - "Look Jacked"
// (packet's Hypertrophy row) and "Strength + Hypertrophy" (packet's
// blended Strength + hypertrophy row, see program_builder._GOAL_WINDOWS).
// Every other sport clears the nudge back to null (balanced/default),
// exactly as before this helper existed - single source of truth for both
// renderSetup's click handler (wizard-setup.js) and jumpToDiscipline's Home
// shortcut (home.js), which used to each hardcode only the "Look Jacked"
// half of this mapping.
function emphasisForSport(sport){
  if(sport === 'Look Jacked') return 'hypertrophy';
  if(sport === 'Strength + Hypertrophy') return 'strength_hypertrophy';
  return null;
}
// Some themes carry a single image, others a rotating array (see Home's
// gallery tiles) - screens that just need one static photo use this instead
// of assuming t.img is always a plain string.
function firstImg(t){ return Array.isArray(t.img) ? t.img[0] : t.img; }
// Like firstImg, but for lists that render several cards of the *same*
// sport at once (e.g. the sc-template picker) - cycles through whatever
// gallery the theme has instead of stamping every card with the same
// single photo. Sports with only one photo just repeat it, same as before.
function nthImg(t, i){
  var imgs = Array.isArray(t.img) ? t.img : (t.img ? [t.img] : []);
  return imgs.length ? imgs[i % imgs.length] : null;
}
// Small inline monogram used wherever a discipline is referenced in running text.
function sportBadge(sport){
  var t = themeFor(sport);
  return '<span class="sport-badge" style="--accent:'+t.accent+'">'+esc(t.mono)+'</span>';
}
// Even smaller — just a colored dot, for tight spaces like calendar cells.
function sportDot(sport){
  var t = themeFor(sport);
  return '<span class="cal-dot" style="background:'+t.accent+'"></span>';
}
// Applies the discipline's whole ambience: accent color across the app,
// a faint ink-wash ring, its native word as a background watermark, and
// now a real photo of the discipline crossfaded in behind everything.
function applyTheme(sport){
  var amb = document.getElementById('ambience');
  if(!sport){ amb.classList.remove('on'); return; }
  var t = themeFor(sport);
  document.body.style.setProperty('--accent', t.accent);
  document.getElementById('ambienceWord').textContent = t.word;
  document.getElementById('ambienceSub').textContent = t.region;
  setAmbiencePhoto(firstImg(t));
  amb.classList.add('on');
}
// Two-layer crossfade: whichever photo layer isn't currently showing gets
// the new image loaded onto it, then fades in while the old one fades out -
// so switching sports drifts from one photo to the next instead of popping.
function setAmbiencePhoto(url){
  if(!url) return;
  var a = document.getElementById('ambiencePhotoA');
  var b = document.getElementById('ambiencePhotoB');
  if(!a || !b) return;
  var aVisible = a.classList.contains('visible');
  var incoming = aVisible ? b : a;
  var outgoing = aVisible ? a : b;
  if(incoming.dataset.src === url){ return; } // already loaded/showing this one
  incoming.dataset.src = url;
  incoming.style.backgroundImage = 'url("'+url+'")';
  incoming.classList.add('visible');
  outgoing.classList.remove('visible');
}
var DIFFICULTY_STARS = {1:'★☆☆☆☆',2:'★★☆☆☆',3:'★★★☆☆',4:'★★★★☆',5:'★★★★★'};
// Keyed by step id (not position) because the exercise-picker step only
// exists in the sequence when Custom Mode is on - see getWizardStepIds().
var WIZARD_STEPS = {
  biometrics: {title:'Your Profile', sub:'Tell us who you are — this only takes a few seconds and it\'s saved right on this device.'},
  discipline: {title:'Choose Discipline', sub:"Pick the sport you train — everything downstream is built around it. Using Custom Mode to pick your own exercises? Tap \"Custom\" if you don't want a specific discipline."},
  equipment:  {title:'Equipment', sub:'What you have access to for this session.'},
  injuries:   {title:'Active Injuries', sub:'Anything that needs to be protected right now — no injuries? Just tap Skip.'},
  readiness:  {title:'Experience &amp; Readiness', sub:'Your strength level, and where you actually are today — not your best day.'},
  exercises:  {title:'Pick Your Exercises', sub:'Custom Mode — search and add exactly what you want in this session.'},
  review:     {title:'Review &amp; Compile', sub:'Confirm your parameters before the engine runs.'}
};
// The step sequence itself, computed live off S.mode - "exercises" only
// appears between equipment/injuries and review when Custom Mode is on.
// Order: profile (name/sex/height/weight/units) -> discipline -> equipment
// -> injuries -> experience/readiness -> (exercises) -> review/generate.
// This whole sequence past "discipline" is Custom Mode's own path now -
// preset (non-custom) discipline picks route straight into the Program
// Builder instead (see the discipline-step branch in btnWizNext,
// injury-browser.js) since the old "Single Session" scope option that used
// to send preset picks down this same path was removed. Equipment and
// injuries used to be two cards stacked on one shared "equipment" step
// (easy to miss the second card on a quick scroll, and no dedicated Skip
// for "no injuries") - now split into their own pages, same pattern as the
// Program wizard's equivalent split (see getProgramWizardStepIds below).
function getWizardStepIds(){
  var ids = ['biometrics','discipline','equipment','injuries','readiness'];
  if(S.mode === 'custom') ids.push('exercises');
  ids.push('review');
  return ids;
}

// Program Builder's own step sequence — fixed (no Custom Mode branch), but
// otherwise the same pattern as WIZARD_STEPS/getWizardStepIds above so a
// 25-field form doesn't land on the person all at once.
var PG_WIZARD_STEPS = {
  basics:     {title:'Program Basics', sub:'Goal, discipline, experience, and how the week is split.'},
  sportFocus: {title:'Sport Focus', sub:'A few questions specific to your discipline, plus any matching FORGE S&amp;C templates.'},
  schedule:   {title:'Schedule &amp; Intensity', sub:'Days per week, program length, and how hard to push it.'},
  equipment:  {title:'Equipment', sub:'What you have access to — reused across the whole program.'},
  injuries:   {title:'Active Injuries', sub:'Anything that needs to be protected across the whole program — no injuries? Just tap Skip.'},
  biometrics: {title:'Your Numbers', sub:'Real numbers unlock real strength-gated work, every week of the program.'},
  customDays: {title:'Build Your Days', sub:'Custom Program — search and add exactly what belongs on each day; the engine still handles progression, deloads, and safety checks.'},
  review:     {title:'Review &amp; Compile', sub:'Confirm your parameters before the engine builds the mesocycle.'}
};
// "customDays" only appears (between biometrics and review) when S.pgMode
// is "custom" - same pattern as getWizardStepIds()/S.mode above, just for
// the Program wizard. Equipment and injuries are their own steps now (see
// getWizardStepIds' comment above for why) instead of two cards sharing
// one step.
function getProgramWizardStepIds(){
  var ids = ['basics','schedule','sportFocus','equipment','injuries','biometrics'];
  // "Sport Focus" only earns its own step when the currently chosen sport
  // actually has something to show there - either an extra sport-specific
  // question (S.scTemplateSportQuestions, from /api/v1/sc-templates/
  // sport-questions - Rugby's Positional Emphasis, MMA's Fight-Style
  // Emphasis, etc.) or any FORGE S&C template coverage at all to browse
  // (S.scTemplateSportsCovered). Reads the live <select> rather than a
  // cached S.* value since the person may have just changed it on this
  // same "basics" step. Both lists default to [] against an older backend
  // (see boot.js), which correctly skips the step everywhere.
  if(!sportHasFocusContent(currentPgSport())){
    ids = ids.filter(function(id){ return id !== 'sportFocus'; });
  }
  // Skip re-asking for biometrics if we already pulled real numbers in from
  // the person's saved profile (see prefillProgramBiometricsFromProfile in
  // program-wizard-steps.js) - avoids asking the same height/weight/1RM
  // questions twice in one visit. Still editable from the Review step.
  if(S.pgBiometricsPrefilled) ids = ids.filter(function(id){ return id !== 'biometrics'; });
  if(S.pgMode === 'custom') ids.push('customDays');
  ids.push('review');
  return ids;
}

// The Program wizard's <select id="pgSport"> is the single source of
// truth for "what sport is currently chosen" mid-wizard (S.sport is only
// the value it was *seeded* from when the step list opened) - both
// getProgramWizardStepIds and renderPgSportFocusStep (program-wizard-
// steps.js) read the live element so a mid-"basics"-step sport change is
// reflected immediately in the very next step, not one step behind.
function currentPgSport(){
  var el = document.getElementById('pgSport');
  return (el && el.value) || S.sport || '';
}

// True if `sport` has anything worth showing on the Sport Focus step -
// its own extra question (Positional Emphasis, Fight-Style Emphasis, ...)
// or any FORGE S&C template to browse at all (even sports with no extra
// question, like Judo/BJJ/Wrestling, still have templates worth
// surfacing - see sc_template_library.py's docstring on why Judo's own
// "dimension" is the sport choice itself, not a second question).
function sportHasFocusContent(sport){
  if(!sport) return false;
  var questions = (S.scTemplateSportQuestions || {})[sport];
  if(questions && questions.length) return true;
  return (S.scTemplateSportsCovered || []).indexOf(sport) !== -1;
}

var S = {
  unit:loadUnit(),
  authToken:loadToken(),
  currentUser:null,
  metadata:null,
  equipmentCatalog:[],
  // Never set true anymore - the quick "how are you feeling today"
  // check-in that used this flag (startQuickSession in home.js) was
  // removed along with the Single Session scope. Left in place because
  // injury-browser.js still branches on it defensively; harmless dead
  // state.
  quickStart:false,
  // True once the person has actually clicked Next past the Train
  // wizard's "Your Profile" (biometrics) step in this session, or had a
  // saved profile restored onto it - see prefillProgramBiometricsFromProfile
  // in program-wizard-steps.js. Distinguishes "the person confirmed these
  // numbers" from the form just sitting at its static HTML defaults
  // (175cm/75kg/10 pull-ups/etc - see index.html), which nobody's actually
  // answered yet.
  bioStepConfirmedThisSession:false,
  athleteName:'', // display name from the Profile step — local-only, never requires an account
  sport:null,
  experience:'Intermediate',
  readiness:80,
  conditioningEmphasis:'Mixed',
  sessionDuration:60, // minutes — sizes exercise_count for a single session (WorkoutRequest.session_duration_minutes)
  mode:'preset',
  emphasis:null, // null (balanced/strength) | 'hypertrophy' | 'strength_hypertrophy' — set by emphasisForSport() from the chosen discipline tile; maps to WorkoutRequest.training_emphasis
  trainScope:null, // 'program' | 'custom' — set programmatically (no longer a UI choice) when the discipline step is confirmed; see the discipline-step branch in btnWizNext, injury-browser.js
  recoveryEnabled:true,
  equipment:new Set(),
  injuries:new Set(),
  // {injury_name: rehab_stage}, only ever holds entries for names also in
  // S.injuries/S.pgInjuries - a stage with its injury unchecked is stale
  // and dropped (see injury-browser.js's chip-uncheck handler). Optional
  // per injury; an entry only appears once the person actually picks a
  // stage for that specific chip. Maps 1:1 to WorkoutRequest/ProgramRequest's
  // own injury_stages: Optional[Dict[str, str]].
  injuryStages:{},
  // {injury_name: side}, same "only holds entries for checked injuries"
  // pattern as injuryStages above (an entry is dropped the moment its
  // injury is unchecked). side is 'left' | 'right' | 'bilateral'. Maps
  // 1:1 to WorkoutRequest/ProgramRequest's own injury_sides:
  // Optional[Dict[str, str]] - only matters for exercises the engine
  // already trains one side at a time (movement_type == 'Unilateral');
  // left unset, the engine treats the injury as bilateral (today's
  // behavior, unchanged).
  injurySides:{},
  // Program Builder gets its own independent injury selection (same pattern
  // as pgEquipmentSet for equipment) so it's a true standalone plan maker -
  // not dependent on running the Train wizard first. Seeded once from
  // S.injuries at startup, then edited independently.
  pgInjuries:new Set(),
  pgInjuryStages:{},
  pgInjurySides:{},
  injOpenSections:new Set(),
  injSearchQuery:'',
  injJointFilter:null,
  // 'joint' (default - Shoulder/Knee/Ankle/...) or 'muscle' (Chest/Back/
  // Legs/... for muscle strains, with ligament/tendon/joint-disorder
  // entries kept in their own "<Joint> (Joints, Ligaments & Tendons)"
  // categories) - see injury-browser.js's renderInjuryBrowser. Switching
  // mode only changes how the same S.injuries selection is browsed/grouped,
  // never what's selected.
  injGroupMode:'joint',
  pgInjOpenSections:new Set(),
  pgInjSearchQuery:'',
  pgInjJointFilter:null,
  pgInjGroupMode:'joint',
  // Equipment browser groups (Free Weights, Machines, ...) start collapsed,
  // same as the injury joint accordion below - opened on click, or
  // auto-opened for a group that already has a selection in it (loadedEquipmentOpen).
  eqOpenGroups:new Set(),
  pgEqOpenGroups:new Set(),
  eqSearchQuery:'',
  pgEqSearchQuery:'',
  // id -> {name, sets, reps, weight_kg, rest_seconds, notes, rpe, rir, tempo,
  // set_type, warmup_sets, group}, insertion order = pick order. The extra
  // fields beyond the original sets/reps/weight/rest/notes are optional and
  // Custom-Mode-only - see custom-workout-builder.js - never sent to the
  // backend, only ever echoed back into ex.prescription client-side
  // (applyCustomPrescriptions in generate.js), same as the original fields.
  selectedExercises:new Map(),
  exPickerQuery:'',
  addExPanelOpen:false, // whether the post-generation "+ Add Exercise" search panel is expanded (session or program-day view)
  addExQuery:'',
  // --- Custom Mode workout builder (see custom-workout-builder.js) ---
  customWorkoutName:'', // free text; 'Custom Workout' is used as the display fallback when empty
  customGroups:{},      // groupId -> {name} — superset/group definitions; a pick's .group field references a key here
  customGroupOrder:[],  // groupId creation order, so groups render in a stable sequence
  customWarmup:[],      // [{id, name, detail}] — a dedicated warm-up section, kept separate from the working exercise list
  customPickerAdvancedOpen:{}, // exId -> true, tracks which chip's Advanced panel is expanded
  customHistoryCache:null, // lazily-fetched /api/v1/sessions history, for "Last time" lookups in the picker
  customEditingWorkoutId:null, // id of the saved custom workout currently loaded for editing, or null (new/unsaved)
  customSafetyWarnings:null, // exId -> {reasons, note} — populated by a review-step precheck against /api/v1/generate-workout
  wizStep:1,
  lastResult:null,
  resultWhyOpen:{},     // exId -> true, tracks which rationale boxes the user expanded (single-workout view)
  sessionLog:{}, // exId -> [{weight,reps,isPR}]
  calDate:new Date(),
  splits:[],
  goals:[],
  lastProgram:null,
  pgSavedProgramId:null, // client_id of the currently-loaded/saved program (for /api/v1/programs upsert), or null (unsaved)
  programWeek:1,
  programDayIndex:0,    // which day of the active week is showing (one day at a time, not the whole week stacked)
  programWhyOpen:{},     // "week|dayIndex::exId" -> true, tracks which rationale boxes the user expanded
  programSessionLog:{}, // "week|dayIndex" -> {exId: {name, sets:[]}}
  programSavedDays:{},  // "week|dayIndex" -> history record id, so a day can be re-saved (updates) instead of duplicating
  pgConditioningEmphasis:'Mixed',
  pgWizStep:1,
  // --- Program Builder Custom Mode (see program-custom-days.js) ---
  // 'preset' (default): unchanged SPLIT_TEMPLATES-driven program. 'custom':
  // built from pgCustomDays instead - see ProgramRequest.mode/custom_days.
  pgMode:'preset',
  // [{id, label, exerciseIds:[...], exerciseNames:{id:name}}, ...] - one
  // entry per day-in-the-rotation, in build order. Cycled to fill
  // days_per_week server-side exactly like a preset split's own day list
  // (see program_builder._cycle_days) - this array does NOT need one entry
  // per days_per_week, just one per distinct day type (e.g. 2 for an A/B
  // split run 4x/week). exerciseNames is display-only (search results carry
  // the name; the request only ever sends exerciseIds).
  pgCustomDays:[],
  pgCustomActiveDayId:null,
  pgExPickerQuery:'',
  condSport:null,
  conditioningRef:null, // cached /api/v1/conditioning-protocols response — sport-agnostic, fetch once
};

