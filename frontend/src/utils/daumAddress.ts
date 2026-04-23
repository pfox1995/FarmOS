export interface DaumPostcodeData {
  address: string;
  addressType: string;
  bname: string;
  buildingName: string;
}

export function formatDaumAddress(data: DaumPostcodeData): string {
  let fullAddress = data.address;
  let extraAddress = '';

  if (data.addressType === 'R') {
    if (data.bname) {
      extraAddress += data.bname;
    }
    if (data.buildingName) {
      extraAddress += extraAddress ? `, ${data.buildingName}` : data.buildingName;
    }
    fullAddress += extraAddress ? ` (${extraAddress})` : '';
  }

  return fullAddress;
}
